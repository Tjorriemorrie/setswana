import pytest

from main.models import AudioClip, Card, Lexeme, Review, Settings

pytestmark = pytest.mark.django_db


def test_settings_load_is_singleton_with_defaults():
    settings = Settings.load()
    assert settings.consolidation_gaps == [1, 1, 2, 3]
    assert Settings.load().pk == settings.pk
    assert str(settings) == 'Settings'


def test_str():
    lexeme = Lexeme.objects.create(setswana='ntlo', english='house', pos='n')
    card = Card.objects.create(lexeme=lexeme)
    review = Review.objects.create(card=card, typed='ntlo', correct=True, rating=Review.Rating.GOOD)
    clip = AudioClip.objects.create(text='ntlo', path='tts/x.wav', voice='mms')
    assert str(lexeme) == 'ntlo (n)'
    assert str(Lexeme(setswana='mma')) == 'mma'
    assert str(review) == 'ntlo [en_to_tn] Good'
    assert str(clip) == 'ntlo'
