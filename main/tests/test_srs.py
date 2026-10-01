from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from main.answers import check_answer, within_one_edit
from main.models import Card, Lexeme, Review, Settings
from main.srs import next_card, submit_answer

pytestmark = pytest.mark.django_db

DAY0 = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


def make_cards(*words):
    cards = []
    for rank, word in enumerate(words, start=1):
        lexeme = Lexeme.objects.create(setswana=word, english=f'en-{word}', rank=rank)
        cards.append(Card.objects.create(lexeme=lexeme))
    return cards


def answer(when, typed=None, easy=False):
    """Answer the next card at `when` (correctly unless `typed` is given); return the card and check."""
    with time_machine.travel(when, tick=False):
        card = next_card()
        result = submit_answer(card, card.lexeme.setswana if typed is None else typed, easy=easy)
    return card, result


def test_check_answer_ratings():
    assert check_answer(' NTLÔ ', 'ntlô').rating == Review.Rating.GOOD
    assert check_answer('ntlo', 'ntlô').rating == Review.Rating.HARD
    assert check_answer('motgo', 'motho').rating == Review.Rating.HARD
    assert check_answer('ga', 'go').rating == Review.Rating.AGAIN
    assert check_answer('mma', 'mma', easy=True).rating == Review.Rating.EASY
    result = check_answer('motxho', 'motlho')
    assert result.diff == [('equal', 'mot'), ('extra', 'x'), ('missing', 'l'), ('equal', 'ho')]
    assert not within_one_edit('ab', 'abcd')
    assert within_one_edit('abd', 'abcd')


def test_word_goes_learning_consolidating_long_term():
    (card,) = make_cards('ntlo')
    t = DAY0
    for minute in range(4):  # introduction + three correct recalls
        answer(t + timedelta(minutes=minute))
    card.refresh_from_db()
    assert card.stage == Card.Stage.CONSOLIDATING
    assert card.due == datetime(2026, 3, 3, tzinfo=UTC)
    with time_machine.travel(t + timedelta(hours=1), tick=False):
        assert next_card() is None  # nothing due, no new words left

    for day in (1, 2, 4):  # consolidation gaps 1, 1, 2
        answer(DAY0 + timedelta(days=day))
    answer(DAY0 + timedelta(days=7), typed='xyz')  # a miss sends it back to the first gap
    card.refresh_from_db()
    assert card.stage == Card.Stage.CONSOLIDATING
    assert card.consolidation_step == 0
    assert card.lapses == 1

    for day in (8, 9, 11, 14):  # gaps 1, 1, 2, 3 again
        answer(DAY0 + timedelta(days=day))
    card.refresh_from_db()
    assert card.stage == Card.Stage.LONG_TERM
    assert card.due > DAY0 + timedelta(days=15)

    later = card.due + timedelta(hours=1)
    answer(later, easy=True)
    card.refresh_from_db()
    assert card.stage == Card.Stage.LONG_TERM
    assert card.due > later + timedelta(days=1)


def test_learning_cards_wait_for_gap_and_reset_on_miss():
    first, second = make_cards('ntlo', 'motho')
    assert answer(DAY0)[0] == first  # introduce
    assert answer(DAY0 + timedelta(minutes=1))[0] == second  # gap of 1 not passed for `first`
    card, result = answer(DAY0 + timedelta(minutes=2), typed='xyz')
    assert card == first
    assert not result.correct
    first.refresh_from_db()
    assert first.session_correct == 0


def test_gate_blocks_new_words():
    cards = make_cards('a1', 'b2', 'c3', 'd4', 'e5', 'f6')
    for i in range(5):
        with time_machine.travel(DAY0 + timedelta(minutes=i), tick=False):
            submit_answer(cards[i], 'x')  # introduce five words: the pool is full
    with time_machine.travel(DAY0 + timedelta(minutes=10), tick=False):
        assert next_card().stage == Card.Stage.LEARNING

    Card.objects.filter(pk__in=[c.pk for c in cards[:5]]).update(
        stage=Card.Stage.CONSOLIDATING, due=DAY0 + timedelta(days=9)
    )
    with time_machine.travel(DAY0 + timedelta(minutes=11), tick=False):
        assert next_card() is None  # the pool has room, but all five answers were wrong

    settings = Settings.load()
    settings.accuracy_threshold = 0
    settings.save()
    with time_machine.travel(DAY0 + timedelta(minutes=12), tick=False):
        assert next_card() == cards[5]
