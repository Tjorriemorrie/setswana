"""Set `Lexeme.frequency` from the NCHLT Setswana corpus frequency list.

`FREQ.LEX.NCHLT.tn.txt` holds `word<TAB>count` lines. Proper names (capitalised words, or words in
the NCHLT named-entity list) are skipped; the rest are matched on their normalised spelling.
"""

import logging
from collections import Counter

from django.conf import settings
from django.db import transaction

from main.models import Lexeme
from main.orthography import normalise

logger = logging.getLogger(__name__)

LEXICA_PATH = ('raw', 'sadilar', 'nchlt_text', 'tn', '3.Lexica')
FREQ_FILE = 'FREQ.LEX.NCHLT.tn.txt'
NE_FILE = 'NELIST.NCHLT.all.txt'


def default_paths():
    """Return the default (frequency list, named-entity list) under DATA_DIR."""
    lexica = settings.DATA_DIR.joinpath(*LEXICA_PATH)
    return lexica / FREQ_FILE, lexica / NE_FILE


def load_names(path):
    """Return the set of named entities, one per line."""
    with path.open(encoding='utf-8') as fh:
        names = {line.strip() for line in fh if line.strip()}
    logger.info('📊 Loaded named-entity list: path=%s, names=%s', path, len(names))
    return names


def parse_frequencies(path, names):
    """Return a Counter {normalised word: count}, skipping proper names and malformed lines."""
    counts = Counter()
    proper = malformed = 0
    with path.open(encoding='utf-8') as fh:
        for line in fh:
            word, _, count = line.strip().partition('\t')
            if not count.isdigit():
                malformed += 1
                continue
            if word != word.lower() or word in names:
                proper += 1
                continue
            counts[normalise(word)] += int(count)
    logger.info(
        '📊 Parsed frequency list: path=%s, words=%s, skipped_proper=%s, malformed=%s',
        path,
        len(counts),
        proper,
        malformed,
    )
    return counts


@transaction.atomic
def import_frequency(freq_path=None, ne_path=None):
    """Set every lexeme's frequency from the corpus list (0 when absent). Returns a dict of counts."""
    default_freq, default_ne = default_paths()
    freq_path = freq_path or default_freq
    ne_path = ne_path or default_ne
    logger.info('📊 Starting frequency import: freq=%s, ne=%s', freq_path, ne_path)

    frequencies = parse_frequencies(freq_path, load_names(ne_path))

    to_update = []
    matched = 0
    lexemes = list(Lexeme.objects.only('id', 'setswana', 'frequency'))
    for lexeme in lexemes:
        frequency = frequencies.get(lexeme.setswana, 0)
        matched += frequency > 0
        if lexeme.frequency != frequency:
            lexeme.frequency = frequency
            to_update.append(lexeme)
    Lexeme.objects.bulk_update(to_update, ['frequency'], batch_size=1000)

    counts = {
        'words': len(frequencies),
        'lexemes': len(lexemes),
        'matched': matched,
        'updated': len(to_update),
    }
    logger.info('✅ Frequency import completed: %s', ', '.join(f'{k}={v}' for k, v in counts.items()))
    return counts
