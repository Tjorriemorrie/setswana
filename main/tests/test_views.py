import pytest
import time_machine

from main.models import Card, Lexeme, Review, Settings

pytestmark = pytest.mark.django_db


def test_practice_flow(client):
    lexeme = Lexeme.objects.create(setswana='ntlô', english='house', pos='n', noun_class='9', rank=1)
    card = Card.objects.create(lexeme=lexeme)

    page = client.get('/')
    assert b'hx-get="/card/"' in page.content

    intro = client.get('/card/').content.decode()
    assert 'New word' in intro and 'ntlô' in intro

    feedback = client.post('/answer/', {'card': card.pk, 'typed': 'ntlo', 'easy': '0'}).content.decode()
    assert 'Introduced' in feedback and 'hx-swap-oob' in feedback

    client.get('/card/')  # the only learning card, shown before its gap
    miss = client.post('/answer/', {'card': card.pk, 'typed': 'pula'}).content.decode()
    assert 'Not quite' in miss and 'dx-missing' in miss


def test_done_card(client):
    Card.objects.create(lexeme=Lexeme.objects.create(setswana='mma', english='mother'), stage=Card.Stage.LONG_TERM)
    Card.objects.filter(stage=Card.Stage.LONG_TERM).update(due='2099-01-01T00:00Z')
    assert 'Done for now' in client.get('/card/').content.decode()


def test_stats_panel(client):
    card = Card.objects.create(lexeme=Lexeme.objects.create(setswana='pula', english='rain', rank=1))
    with time_machine.travel('2026-09-29 12:00Z'):
        Review.objects.create(card=card, typed='pula', correct=True, rating=Review.Rating.GOOD)
    with time_machine.travel('2026-09-30 12:00Z'):
        Review.objects.create(card=card, typed='pul', correct=False, rating=Review.Rating.AGAIN)
        Card.objects.filter(pk=card.pk).update(stage=Card.Stage.CONSOLIDATING, due='2026-10-01T00:00Z')
        stats = client.get('/stats/').content.decode()
    assert '2</span>' in stats and 'days in a row' in stats
    assert 'waiting' in stats and 'no practice' in stats


def test_settings_change_the_gate(client):
    Card.objects.create(lexeme=Lexeme.objects.create(setswana='pula', english='rain', rank=1))
    assert 'value="1, 1, 2, 3"' in client.get('/settings/').content.decode()

    data = {
        'learning_pool_cap': 0,
        'accuracy_threshold': 90,
        'accuracy_window': 10,
        'session_correct_required': 2,
        'consolidation_gaps': '1 2, 4',
        'target_retention': 92,
    }
    saved = client.post('/settings/', data)
    assert saved['HX-Trigger'] == 'settings-saved' and 'Settings saved.' in saved.content.decode()
    assert Settings.load().consolidation_gaps == [1, 2, 4]
    assert 'Done for now' in client.get('/card/').content.decode()

    rejected = client.post('/settings/', {**data, 'consolidation_gaps': '1, x'}).content.decode()
    assert 'Not saved' in rejected
