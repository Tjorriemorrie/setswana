"""Import the hand-curated Peace Corps survival vocabulary (`data/curated/peace_corps.yaml`).

Each word is matched to an existing lexeme on its diacritic-free spelling and part of speech, or on
its spelling alone when exactly one lexeme has it; otherwise a new lexeme is created. Matched
lexemes keep their spelling (other importers match on it) but take the curated gloss, and every
curated lexeme gets `curated_order`, its position in the file, which `build_ranking` ranks first.
"""

import logging

import yaml
from django.conf import settings
from django.db import transaction

from main.models import Lexeme
from main.orthography import normalise, strip_diacritics

logger = logging.getLogger(__name__)

SOURCE = 'peace_corps'
YAML_PATH = ('curated', 'peace_corps.yaml')


def default_path():
    """Return the default curated YAML path under DATA_DIR."""
    return settings.DATA_DIR.joinpath(*YAML_PATH)


def load_words(path):
    """Return the curated words in file order as dicts with setswana, pos, english and plural."""
    with path.open(encoding='utf-8') as fh:
        lessons = yaml.safe_load(fh)['lessons']
    words = []
    seen = set()
    for lesson in lessons:
        for entry in lesson['words']:
            word = {
                'setswana': normalise(entry['setswana']),
                'pos': entry['pos'],
                'english': entry['english'].strip(),
                'plural': normalise(entry.get('plural', '')),
            }
            key = (strip_diacritics(word['setswana']), word['pos'])
            if key in seen:
                logger.error(
                    '❌ Duplicate curated word: setswana=%s, pos=%s, lesson=%s, path=%s',
                    word['setswana'],
                    word['pos'],
                    lesson['lesson'],
                    path,
                )
                raise ValueError(f'Duplicate curated word {key} in {path}')
            seen.add(key)
            words.append(word)
    logger.info('🇧🇼 Loaded curated words: path=%s, lessons=%s, words=%s', path, len(lessons), len(words))
    return words


@transaction.atomic
def import_peace_corps(path=None):
    """Upsert the curated words and set their `curated_order`. Returns a dict of counts."""
    path = path or default_path()
    logger.info('🇧🇼 Starting Peace Corps import: path=%s', path)
    words = load_words(path)

    by_key = {}
    by_spelling = {}
    for lexeme in Lexeme.objects.all():
        plain = strip_diacritics(lexeme.setswana)
        by_key.setdefault((plain, lexeme.pos), []).append(lexeme)
        by_spelling.setdefault(plain, []).append(lexeme)

    # Part-of-speech matches first, so that a spelling-only match never takes a lexeme another word
    # matches exactly. Among spelling variants (ntlo, ntlô), the same spelling wins, then the most frequent.
    matches = {}
    for order, word in enumerate(words, start=1):
        if variants := by_key.get((strip_diacritics(word['setswana']), word['pos'])):
            matches[order] = max(variants, key=lambda lx: (lx.setswana == word['setswana'], lx.frequency))
    matched_pos = len(matches)
    claimed = {lexeme.pk for lexeme in matches.values()}
    for order, word in enumerate(words, start=1):
        candidates = by_spelling.get(strip_diacritics(word['setswana']), [])
        if order not in matches and len(candidates) == 1 and candidates[0].pk not in claimed:
            # Another source labelled the part of speech differently; its label is kept so it still matches.
            matches[order] = candidates[0]
            claimed.add(candidates[0].pk)

    to_create = []
    to_update = []
    for order, word in enumerate(words, start=1):
        lexeme = matches.get(order)
        if lexeme is None:
            to_create.append(
                Lexeme(
                    setswana=word['setswana'],
                    pos=word['pos'],
                    english=word['english'],
                    plural=word['plural'],
                    curated_order=order,
                    sources=[SOURCE],
                )
            )
            continue
        lexeme.english = word['english']
        lexeme.plural = word['plural'] or lexeme.plural
        lexeme.curated_order = order
        lexeme.sources = lexeme.sources if SOURCE in lexeme.sources else [*lexeme.sources, SOURCE]
        to_update.append(lexeme)
    logger.info(
        '🇧🇼 Matched curated words: words=%s, matched_pos=%s, matched_spelling=%s, to_create=%s',
        len(words),
        matched_pos,
        len(matches) - matched_pos,
        len(to_create),
    )

    # Words removed from the file lose their curated position (and so their top rank).
    dropped = list(Lexeme.objects.filter(curated_order__isnull=False).exclude(pk__in=claimed))
    for lexeme in dropped:
        lexeme.curated_order = None
        lexeme.sources = [source for source in lexeme.sources if source != SOURCE]

    Lexeme.objects.bulk_create(to_create, batch_size=1000)
    Lexeme.objects.bulk_update(to_update, ['english', 'plural', 'curated_order', 'sources'], batch_size=1000)
    Lexeme.objects.bulk_update(dropped, ['curated_order', 'sources'], batch_size=1000)
    counts = {
        'words': len(words),
        'matched': len(to_update),
        'created': len(to_create),
        'dropped': len(dropped),
    }
    logger.info('✅ Peace Corps import completed: %s', ', '.join(f'{k}={v}' for k, v in counts.items()))
    return counts
