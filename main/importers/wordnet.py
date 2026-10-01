"""Import Setswana lemmas from the African Wordnet, glossed via Princeton WordNet 2.0.

Each `LexicalEntry` lemma points at synsets `awn_tsn-ENG20-<offset>-<pos>`; the offset is a byte
offset into PWN 2.0 `dict/data.<pos>`, whose first synonyms become the English gloss.
"""

import logging
import re
import xml.etree.ElementTree as ET

from django.conf import settings
from django.db import transaction

from main.models import Lexeme
from main.orthography import normalise

logger = logging.getLogger(__name__)

SOURCE = 'wordnet'
LMF_PATH = ('raw', 'sadilar', 'african_wordnet', 'African Wordnet Setswana', 'wntsn-lmf.xml')
PWN_DICT_PATH = ('raw', 'princeton_wordnet_2.0', 'WordNet-2.0', 'dict')
PWN_FILES = {'n': 'data.noun', 'v': 'data.verb', 'a': 'data.adj', 'r': 'data.adv'}

WORDS_PER_SENSE = 3
MAX_SENSES = 3

_SYNSET_RE = re.compile(r'ENG20-(\d{8})-([nvar])$')
_CHAR_FIXES = str.maketrans({'ȏ': 'ô', 'ȇ': 'ê', 'á': 'a'})
_VALID_LEMMA_RE = re.compile(r"^[a-zêôš' -]+$")
_ADJ_MARKER_RE = re.compile(r'\((?:a|p|ip)\)$')


def default_paths():
    """Return the default (LMF file, PWN dict dir) under DATA_DIR."""
    return settings.DATA_DIR.joinpath(*LMF_PATH), settings.DATA_DIR.joinpath(*PWN_DICT_PATH)


def clean_lemma(raw):
    """Return the lemma in normalised modern spelling, or None if it is unusable."""
    if raw != raw.lower():
        return None  # proper names (James, Jôbô, …)
    lemma = normalise(raw.lstrip('*').translate(_CHAR_FIXES))
    return lemma if _VALID_LEMMA_RE.match(lemma) else None


def parse_lmf(path):
    """Return [(lemma, pos, [(offset, pos), …])] for every usable lexical entry."""
    entries = []
    skipped = 0
    for _, elem in ET.iterparse(path):  # noqa: S314 - local, trusted data file
        if elem.tag != 'LexicalEntry':
            continue
        lemma_elem = elem.find('Lemma')
        lemma = clean_lemma(lemma_elem.get('writtenForm', ''))
        synsets = [m.groups() for s in elem.iter('Sense') if (m := _SYNSET_RE.search(s.get('synset', '')))]
        if lemma:
            entries.append((lemma, lemma_elem.get('partOfSpeech', ''), synsets))
        else:
            skipped += 1
        elem.clear()
    logger.info('📚 Parsed African Wordnet LMF: path=%s, entries=%s, skipped_lemmas=%s', path, len(entries), skipped)
    return entries


def load_pwn_words(dict_dir, wanted):
    """Return {(offset, pos): [english words]} for the wanted synsets, read from PWN data files."""
    words = {}
    for pos in sorted({pos for _, pos in wanted}):
        offsets = {offset for offset, p in wanted if p == pos}
        with (dict_dir / PWN_FILES[pos]).open(encoding='latin-1') as fh:
            for line in fh:
                offset = line[:8]
                if offset not in offsets:
                    continue
                fields = line.split(' | ')[0].split()
                count = int(fields[3], 16)
                synonyms = fields[4 : 4 + 2 * count : 2]
                words[(offset, pos)] = [_ADJ_MARKER_RE.sub('', w).replace('_', ' ') for w in synonyms]
    logger.info('📚 Loaded PWN synsets: wanted=%s, found=%s', len(wanted), len(words))
    return words


def build_gloss(synsets, pwn_words):
    """Return the English gloss: up to 3 words from each of the first 3 found senses, deduplicated."""
    senses = []
    seen = set()
    for key in synsets:
        sense = [w for w in pwn_words.get(key, [])[:WORDS_PER_SENSE] if w.lower() not in seen]
        if sense:
            seen.update(w.lower() for w in sense)
            senses.append(', '.join(sense))
        if len(senses) == MAX_SENSES:
            break
    return '; '.join(senses)


@transaction.atomic
def import_wordnet(lmf_path=None, pwn_dir=None):
    """Upsert wordnet lexemes. Returns a dict of counts."""
    default_lmf, default_pwn = default_paths()
    lmf_path = lmf_path or default_lmf
    pwn_dir = pwn_dir or default_pwn
    logger.info('📚 Starting WordNet import: lmf=%s, pwn_dir=%s', lmf_path, pwn_dir)

    entries = parse_lmf(lmf_path)
    pwn_words = load_pwn_words(pwn_dir, {key for _, _, synsets in entries for key in synsets})

    existing = {(lx.setswana, lx.pos): lx for lx in Lexeme.objects.all()}
    seen = set()
    to_create = {}
    to_update = {}
    no_gloss = duplicates = 0
    for lemma, pos, synsets in entries:
        gloss = build_gloss(synsets, pwn_words)
        if not gloss:
            no_gloss += 1
            continue
        key = (lemma, pos)
        if key in seen:  # the first entry wins when cleaning merges two lemmas
            duplicates += 1
            continue
        seen.add(key)
        lexeme = existing.get(key)
        if lexeme is None:
            to_create[key] = Lexeme(setswana=lemma, pos=pos, english=gloss, sources=[SOURCE])
            continue
        # WordNet owns the gloss until another source has contributed to the lexeme.
        changed = False
        if (not lexeme.english or lexeme.sources == [SOURCE]) and lexeme.english != gloss:
            lexeme.english = gloss
            changed = True
        if SOURCE not in lexeme.sources:
            lexeme.sources = [*lexeme.sources, SOURCE]
            changed = True
        if changed:
            to_update[key] = lexeme
    logger.info(
        '📚 Matched entries: entries=%s, to_create=%s, to_update=%s, no_gloss=%s, duplicates=%s',
        len(entries),
        len(to_create),
        len(to_update),
        no_gloss,
        duplicates,
    )

    Lexeme.objects.bulk_create(to_create.values(), batch_size=1000)
    Lexeme.objects.bulk_update(to_update.values(), ['english', 'sources'], batch_size=1000)
    counts = {
        'entries': len(entries),
        'created': len(to_create),
        'updated': len(to_update),
        'unchanged': len(seen) - len(to_create) - len(to_update),
        'no_gloss': no_gloss,
        'duplicates': duplicates,
    }
    logger.info('✅ WordNet import completed: %s', ', '.join(f'{k}={v}' for k, v in counts.items()))
    return counts
