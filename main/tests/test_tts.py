import numpy as np
import pytest

from main import tts
from main.models import AudioClip, Card, Lexeme

pytestmark = pytest.mark.django_db


@pytest.fixture
def fake_model(settings, tmp_path, monkeypatch):
    """Point MEDIA_ROOT at a temp dir and replace the model with silence; return the rendered texts."""
    settings.MEDIA_ROOT = tmp_path
    rendered = []

    def render(text):
        if text == '...':
            raise ValueError(text)
        rendered.append(text)
        return 16000, np.zeros(160, dtype=np.float32)

    monkeypatch.setattr(tts, 'render', render)
    return rendered


def test_synthesize_caches(fake_model, tmp_path):
    path = tts.synthesize(' Dumêla ')
    assert path.exists() and path.parent == tmp_path / 'tts'
    assert tts.synthesize('dumêla') == path
    assert fake_model == ['dumêla']
    assert AudioClip.objects.get().path == f'tts/{path.name}'


def test_pregenerate(fake_model):
    for rank, word in enumerate(['mma', '...', 'ntlo'], start=1):
        Lexeme.objects.create(setswana=word, rank=rank)
    tts.synthesize('ntlo')
    assert tts.pregenerate(10) == {'generated': 1, 'cached': 1, 'failed': 1}


def test_audio_view_and_listening_card(fake_model, client):
    lexeme = Lexeme.objects.create(setswana='ntlo', english='house', rank=1)
    response = client.get(f'/audio/{lexeme.pk}/')
    assert response.status_code == 302 and response.url.startswith('/media/tts/')
    assert client.get(f'/audio/{Lexeme.objects.create(setswana="...").pk}/').status_code == 404

    card = Card.objects.create(lexeme=lexeme, direction=Card.Direction.AUDIO_TO_TN)
    page = client.get('/card/').content.decode()
    assert 'listen-band' in page and 'house' not in page
    feedback = client.post('/answer/', {'card': card.pk, 'typed': 'ntlo'}).content.decode()
    assert 'Good' in feedback and 'data-autoplay' in feedback
    card.refresh_from_db()
    assert card.session_correct == 1
