"""Setswana spelling helpers: normalisation and diacritic stripping."""

import unicodedata


def normalise(text):
    """Return text in NFC, lowercased, with whitespace collapsed to single spaces."""
    return ' '.join(unicodedata.normalize('NFC', text).lower().split())


def strip_diacritics(text):
    """Return text without combining marks, so ê/ô/š become e/o/s."""
    decomposed = unicodedata.normalize('NFD', text)
    return unicodedata.normalize('NFC', ''.join(ch for ch in decomposed if not unicodedata.combining(ch)))
