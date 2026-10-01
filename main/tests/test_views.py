import pytest

from main.models import Card, Lexeme

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
