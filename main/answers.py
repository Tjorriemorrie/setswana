"""Checking a typed answer against the expected Setswana word: rating plus a character diff."""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

from main.models import Review
from main.orthography import normalise, strip_diacritics

logger = logging.getLogger(__name__)

# Typos (edit distance 1) are only forgiven in words at least this long, so that short words such as
# `go` and `ga` stay distinct.
MIN_TYPO_LENGTH = 4


@dataclass(frozen=True)
class AnswerCheck:
    correct: bool
    rating: int
    diff: list  # (tag, text) segments; tag is 'equal', 'extra' (typed only) or 'missing' (expected only)


def within_one_edit(a, b):
    """Return whether a and b differ by at most one insertion, deletion or substitution."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :] or (len(a) == len(b) and a[i + 1 :] == b[i + 1 :])


def char_diff(typed, expected):
    """Return the character diff from typed to expected as (tag, text) segments."""
    segments = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=typed, b=expected, autojunk=False).get_opcodes():
        if tag == 'equal':
            segments.append(('equal', expected[j1:j2]))
            continue
        if i2 > i1:
            segments.append(('extra', typed[i1:i2]))
        if j2 > j1:
            segments.append(('missing', expected[j1:j2]))
    return segments


def check_answer(typed, expected, easy=False):
    """Grade a typed answer: wrong → Again, near miss → Hard, exact → Good (or Easy when asked)."""
    typed_n, expected_n = normalise(typed), normalise(expected)
    bare_typed, bare_expected = strip_diacritics(typed_n), strip_diacritics(expected_n)
    if typed_n == expected_n:
        rating, reason = Review.Rating.GOOD, 'exact'
    elif bare_typed == bare_expected:
        rating, reason = Review.Rating.HARD, 'missing diacritics'
    elif bare_typed and len(bare_expected) >= MIN_TYPO_LENGTH and within_one_edit(bare_typed, bare_expected):
        rating, reason = Review.Rating.HARD, 'typo'
    else:
        rating, reason = Review.Rating.AGAIN, 'wrong'
    correct = rating != Review.Rating.AGAIN
    if correct and easy:
        rating = Review.Rating.EASY
    result = AnswerCheck(correct=correct, rating=rating, diff=char_diff(typed_n, expected_n))
    logger.info(
        '📝 Checked answer: typed=%r, expected=%r, reason=%s, rating=%s', typed_n, expected_n, reason, rating.label
    )
    return result
