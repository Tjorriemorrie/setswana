"""Import Brown's *Secwana Dictionary* (1925) from its OCR text.

Only the Secwana-English half is read. Entries look like `Headword, pos., [grammar notes,] gloss;
gloss. Examples…`, wrapped and hyphenated over several lines and interleaved with page headers and
OCR noise. Headwords are converted to modern spelling (`main/orthography.py`); when a rule-based
spelling is unknown, alternatives are checked against existing lexemes and the NCHLT corpus.
"""

import logging
import re

from django.conf import settings
from django.db import transaction

from main.importers.frequency import default_paths as frequency_paths
from main.models import Lexeme
from main.orthography import modern_candidates, strip_diacritics

logger = logging.getLogger(__name__)

SOURCE = 'brown'
TEXT_PATH = ('raw', 'archive_org', 'brown_1885_secwana_dictionary.txt')

MAX_SENSES = 3
MAX_GLOSS_LENGTH = 100

_SECTION_START_RE = re.compile(r'^\s*SECWANA\s*-\s*ENGLISH\s*$')
_SECTION_END_RE = re.compile(r'^\s*ENGLISH\s*-\s*SECWANA')
_PAGE_HEADER_RE = re.compile(r'^\s*(\d+\s+)?[A-Z]+\s*[—-]\s*[A-Z]+(\s+\d+)?\s*$')
_NOISE_PREFIX_RE = re.compile(r"^[\s|'‘’_.,:;\-]+")
_ENTRY_RE = re.compile(r"^([A-Z][a-zé'-]+), (.*)$")
# A headword line continues with a part of speech, a capitalised gloss, or a grammar note.
_ENTRY_TAIL_RE = re.compile(r'^([a-z][a-z. ]{0,18}\.,|[A-Z]|from |pl\. |pft\.)')
_POS_RE = re.compile(r'^([a-z][a-z. ]{0,18}?\.),\s*')
_ABBREVIATIONS = (
    'pft|pift|pit|plt|pf|no pl|pl|sing|ref|rev|rever|rec|voc|caus|dim|redup|pass|prep|intens|recip|rel|freq|lit|'
    'dem|pron|pers|per|poss|emph|emp|inter|imper|infin|subj|neg|fut|aux|conj|adj|adv|interj|etc|v|t|i|n'
)
# Grammar notes ("pft. bogile", "from gata", "caus. of boga", "1st per.") that precede or interrupt the meaning.
_NOTE_RE = re.compile(
    rf'^(({_ABBREVIATIONS})\.|(ist|1st|2nd|3rd) pers?\.|'
    r'(from|froin|probably|used with|same as|form of|followed by|governs)\b|fem$|or \w+$)',
    re.IGNORECASE,
)
# A full stop (or ! or ?) ends the gloss unless it ends an abbreviation.
_SENTENCE_END_RE = re.compile(rf'(?<![a-z])(?!(?:{_ABBREVIATIONS})\.)([A-Za-z]+)[.!?](\s|$)')
_PARENS_RE = re.compile(r'\([^)]*\)')
# A second part of speech starts another meaning ("v.t., fit badly"), which is left out.
_POS_MARKER_RE = re.compile(r'\b(n|v\.t|v\.i|v|adj|adv|conj|interj)\.,')
_JUNK_RE = re.compile(r'[|_—©®¢«»£°¥€§~]|(?<=\s)[.:-](?=\s)')
_SPACE_BEFORE_PUNCT_RE = re.compile(r'\s+(?=[,;])')
POS_MAP = {
    'n': 'n',
    'pl': 'n',
    'v': 'v',
    'vi': 'v',
    'u': 'v',
    'y': 'v',
    'p': 'v',
    'aux': 'v',
    'adj': 'a',
    'dj': 'a',
    'demon': 'a',
    'adv': 'r',
    'pron': 'pron',
    'dem': 'pron',
    'emph': 'pron',
    'emp': 'pron',
    'pers': 'pron',
    'per': 'pron',
    'poss': 'pron',
    'inter': 'pron',
    'conj': 'conj',
    'prep': 'prep',
    'interj': 'interj',
    'nu': 'num',
}


def default_path():
    """Return the default OCR text path under DATA_DIR."""
    return settings.DATA_DIR.joinpath(*TEXT_PATH)


def section_lines(path):
    """Return the lines of the Secwana-English half, without page headers and blank lines."""
    lines = []
    inside = False
    headers = 0
    with path.open(encoding='utf-8') as fh:
        for line in fh:
            if not inside:
                inside = bool(_SECTION_START_RE.match(line))
                continue
            if _SECTION_END_RE.match(line):
                break
            if _PAGE_HEADER_RE.match(line):
                headers += 1
                continue
            line = _NOISE_PREFIX_RE.sub('', line).rstrip()
            if any(ch.islower() for ch in line):
                lines.append(line)
    logger.info('📖 Read Secwana-English section: path=%s, lines=%s, page_headers=%s', path, len(lines), headers)
    return lines


def split_entries(lines):
    """Return [(headword, text)] with wrapped lines joined and line-end hyphenation undone."""
    entries = []
    for line in lines:
        match = _ENTRY_RE.match(line)
        if match and _ENTRY_TAIL_RE.match(match.group(2)):
            entries.append([match.group(1), match.group(2)])
        elif entries:
            text = entries[-1][1]
            entries[-1][1] = text[:-1] + line if text.endswith('-') else f'{text} {line}'
    return [(headword, text) for headword, text in entries]


def parse_pos(text):
    """Return (pos, rest): the mapped part of speech ('' when absent or unknown) and the remaining text."""
    match = _POS_RE.match(text)
    if not match:
        return '', text
    first = match.group(1).replace(' ', '').split('.')[0]
    return POS_MAP.get(first, ''), text[match.end() :]


def parse_gloss(text):
    """Return a short English gloss: the first senses of the definition's first sentence."""
    text = _JUNK_RE.sub(' ', _PARENS_RE.sub('', text)).replace('@', 'a')
    text = _SPACE_BEFORE_PUNCT_RE.sub('', text)
    if end := _SENTENCE_END_RE.search(text):
        text = text[: end.end(1)]
    text = _POS_MARKER_RE.split(text, maxsplit=1)[0]
    senses = []
    for part in text.split(';'):
        pieces = [' '.join(p.split()) for p in part.split(',')]
        sense = ', '.join(p for p in pieces if p and not _NOTE_RE.match(p)).strip(' .:-')
        if not sense or not any(ch.isalpha() for ch in sense):
            continue
        first_word = sense.split()[0]
        if first_word != 'I' and (len(first_word) == 1 or not first_word.isupper()):  # keep "I" and acronyms
            sense = sense[0].lower() + sense[1:]
        if sense not in senses:
            senses.append(sense)
        if len(senses) == MAX_SENSES:
            break
    return shorten('; '.join(senses))


def shorten(gloss):
    """Return the gloss cut at a sense or comma boundary to at most MAX_GLOSS_LENGTH characters."""
    if len(gloss) > MAX_GLOSS_LENGTH:
        gloss = gloss[:MAX_GLOSS_LENGTH].rsplit(';', 1)[0].rsplit(',', 1)[0]
    return gloss


def merge_glosses(glosses):
    """Return one gloss for homographs: every homograph's first sense, then their other senses."""
    senses = [gloss.split('; ') for gloss in glosses]
    ordered = [sense[0] for sense in senses] + [s for sense in senses for s in sense[1:]]
    return shorten('; '.join(dict.fromkeys(ordered)))


def parse_dictionary(path):
    """Return [(old_headword, pos, gloss)] for every entry with a gloss."""
    entries = split_entries(section_lines(path))
    parsed = []
    no_gloss = 0
    for headword, text in entries:
        pos, rest = parse_pos(text)
        gloss = parse_gloss(rest)
        if gloss:
            parsed.append((headword.lower(), pos, gloss))
        else:
            no_gloss += 1
    with_pos = sum(1 for _, pos, _ in parsed if pos)
    logger.info(
        '📖 Parsed Brown entries: entries=%s, glossed=%s, with_pos=%s, no_gloss=%s',
        len(entries),
        len(parsed),
        with_pos,
        no_gloss,
    )
    return parsed


def known_words(freq_path):
    """Return the diacritic-free modern spellings we trust: other sources' lexemes plus corpus words."""
    # Lexemes that only Brown attests are excluded, so that re-runs pick the same spellings.
    spellings = Lexeme.objects.exclude(sources=[SOURCE]).values_list('setswana', flat=True)
    words = {strip_diacritics(s) for s in spellings}
    lexemes = len(words)
    with freq_path.open(encoding='utf-8') as fh:
        words.update(strip_diacritics(line.split('\t', 1)[0]) for line in fh if line[:1].islower())
    logger.info('📖 Loaded known modern words: lexemes=%s, total=%s', lexemes, len(words))
    return words


def to_modern(old, known):
    """Return (modern spelling, attested): the first known candidate, else the rule-based spelling."""
    candidates = modern_candidates(old)
    for candidate in candidates:
        if candidate in known:
            return candidate, True
    return candidates[0], False


@transaction.atomic
def import_brown(text_path=None, freq_path=None):
    """Merge Brown's glosses into existing lexemes and add the rest as new lexemes. Returns counts."""
    text_path = text_path or default_path()
    freq_path = freq_path or frequency_paths()[0]
    logger.info('📖 Starting Brown import: text=%s, freq=%s', text_path, freq_path)

    entries = parse_dictionary(text_path)
    known = known_words(freq_path)

    by_key = {}
    by_spelling = {}
    for lexeme in Lexeme.objects.all():
        plain = strip_diacritics(lexeme.setswana)
        by_key.setdefault((plain, lexeme.pos), lexeme)
        by_spelling.setdefault(plain, lexeme)

    # Homographs with the same modern spelling and part of speech share one lexeme.
    grouped = {}
    attested = 0
    for old, pos, gloss in entries:
        modern, is_known = to_modern(old, known)
        attested += is_known
        grouped.setdefault((modern, pos), (old, []))[1].append(gloss)

    claimed = set()
    to_create = []
    to_update = {}
    matched = unclaimed = 0
    for (modern, pos), (old, glosses) in grouped.items():
        gloss = merge_glosses(glosses)
        lexeme = by_key.get((modern, pos)) or (by_spelling.get(modern) if not pos else None)
        if lexeme is None:
            to_create.append(Lexeme(setswana=modern, pos=pos, english=gloss, sources=[SOURCE], notes=f'Brown: {old}'))
            continue
        if lexeme.pk in claimed:  # an entry without a part of speech that matched an already merged lexeme
            unclaimed += 1
            continue
        claimed.add(lexeme.pk)
        # Matches with another source's lexeme; stable across re-runs, unlike matches with Brown's own.
        matched += lexeme.sources != [SOURCE]
        # Brown's glosses are plainer than WordNet's, so Brown owns the gloss of every lexeme it matches.
        if lexeme.english != gloss or SOURCE not in lexeme.sources:
            lexeme.english = gloss
            lexeme.sources = lexeme.sources if SOURCE in lexeme.sources else [*lexeme.sources, SOURCE]
            to_update[lexeme.pk] = lexeme
    logger.info(
        '📖 Matched entries: entries=%s, headwords=%s, matched_other_sources=%s, match_rate=%.1f%%, to_create=%s, '
        'to_update=%s, attested_spellings=%s, unclaimed=%s',
        len(entries),
        len(grouped),
        matched,
        100 * matched / max(len(grouped), 1),
        len(to_create),
        len(to_update),
        attested,
        unclaimed,
    )

    Lexeme.objects.bulk_create(to_create, batch_size=1000)
    Lexeme.objects.bulk_update(to_update.values(), ['english', 'sources'], batch_size=1000)
    counts = {
        'entries': len(entries),
        'matched': matched,
        'created': len(to_create),
        'updated': len(to_update),
        'attested': attested,
        'homographs': len(entries) - len(grouped),
    }
    logger.info('✅ Brown import completed: %s', ', '.join(f'{k}={v}' for k, v in counts.items()))
    return counts
