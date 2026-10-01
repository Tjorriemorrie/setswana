"""Setswana spelling helpers: normalisation, diacritic stripping and old-to-modern spelling."""

import re
import unicodedata


def normalise(text):
    """Return text in NFC, lowercased, with whitespace collapsed to single spaces."""
    return ' '.join(unicodedata.normalize('NFC', text).lower().split())


def strip_diacritics(text):
    """Return text without combining marks, so ê/ô/š become e/o/s."""
    decomposed = unicodedata.normalize('NFD', text)
    return unicodedata.normalize('NFC', ''.join(ch for ch in decomposed if not unicodedata.combining(ch)))


# Brown's dictionary (1925) uses the 1910 conference spelling. Applied in order to a lowercased,
# diacritic-free headword; each rule raised the share of headwords found in the modern corpus. The
# old open-vowel marks (é/ó) are dropped: the OCR confuses them, and answers are accepted without
# diacritics anyway.
OLD_TO_MODERN_RULES = (
    (re.compile(r'd$'), 'o'),  # OCR reads a final ó as d (bogamó → "bogamd")
    (re.compile(r'd(?=[^aeiouw])'), 'o'),  # …and as d before a consonant (bogóba → "bogdba", góla → "gdla")
    (re.compile(r'tih'), 'tlh'),  # OCR reads lh as ih after t (tlhogo → "tihogo")
    (re.compile(r'(?<!t)sh'), 's'),  # shupa → supa (tsh is kept)
    (re.compile(r'c'), 'ts'),  # coma → tsoma, Secwana → Setswana, chaka → tshaka
    (re.compile(r'(?<!n)y'), 'j'),  # yaka → jaka, diyo → dijo (ny is kept)
    (re.compile(r'(?<=[aeiou])e(?=[aou])|^e(?=[aou])'), 'y'),  # tsamaea → tsamaya, ea → ya
)

# Setlhaping h is f in the modern standard (gauhi → gaufi); only tried as an alternative spelling.
_LONE_H_RE = re.compile(r'(?<![ptks])h')
MAX_VARIANTS = 8


def modernise(old):
    """Return a headword in Brown's old spelling converted to modern spelling, without diacritics."""
    word = strip_diacritics(normalise(old))
    for pattern, replacement in OLD_TO_MODERN_RULES:
        word = pattern.sub(replacement, word)
    return word


def modern_candidates(old):
    """Return plausible modern spellings of an old headword, the rule-based one first."""
    base = modernise(old)
    candidates = [base]
    if base.endswith('oo'):  # the OCR sometimes keeps the o of a final ó as well (modumó → "modumod")
        candidates.append(base[:-1])
    positions = [m.start() for m in _LONE_H_RE.finditer(base)]
    for mask in range(1, min(2 ** len(positions), MAX_VARIANTS)):
        chars = list(base)
        for bit, pos in enumerate(positions):
            if mask >> bit & 1:
                chars[pos] = 'f'
        candidates.append(''.join(chars))
    return candidates
