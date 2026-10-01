import pytest
from django.core.management import call_command

from main.importers.frequency import FREQ_FILE, LEXICA_PATH, NE_FILE
from main.models import Card, Lexeme, Review

pytestmark = pytest.mark.django_db

FREQ = 'ya\t500\r\nmotho\t300\r\nntlo\t100\r\nMotho\t50\r\nmma\t80\r\nisiZulu\t40\r\nbroken line\r\n'
NELIST = 'isiZulu\r\nGaborone\r\n'


@pytest.fixture
def data_dir(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    lexica = tmp_path.joinpath(*LEXICA_PATH)
    lexica.mkdir(parents=True)
    (lexica / FREQ_FILE).write_text(FREQ, encoding='utf-8')
    (lexica / NE_FILE).write_text(NELIST, encoding='utf-8')
    return tmp_path


def test_frequency_and_ranking(data_dir):
    Lexeme.objects.create(setswana='ya', pos='v', english='go')
    Lexeme.objects.create(setswana='motho', pos='n', english='person')
    Lexeme.objects.create(setswana='ntlo', pos='n', english='house')
    Lexeme.objects.create(setswana='mma', pos='n')
    Lexeme.objects.create(setswana='isizulu', pos='n', english='Zulu')
    dropped = Lexeme.objects.create(setswana='pula', pos='n', english='rain', rank=1)
    practised = Lexeme.objects.create(setswana='nama', pos='n', english='meat', rank=2)
    Card.objects.create(lexeme=dropped)
    Review.objects.create(card=Card.objects.create(lexeme=practised), correct=True, rating=3)

    call_command('import_frequency')
    call_command('build_ranking', show=5)
    call_command('build_ranking')

    assert dict(Lexeme.objects.values_list('setswana', 'frequency'))['motho'] == 300
    assert list(Lexeme.objects.filter(rank__isnull=False).values_list('setswana', 'rank')) == [
        ('motho', 1),
        ('ntlo', 2),
    ]
    assert sorted(Card.objects.values_list('lexeme__setswana', flat=True)) == ['motho', 'nama', 'ntlo']
