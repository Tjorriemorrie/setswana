import pytest
from django.core.management import call_command

from main.importers.brown import TEXT_PATH
from main.importers.frequency import FREQ_FILE, LEXICA_PATH
from main.models import Lexeme
from main.orthography import modernise

pytestmark = pytest.mark.django_db

TEXT = """SECWANA DICTIONARY

SECWANA - ENGLISH

Motho, n., pl. batho, A person; a
human being. Motho eo o molemo, a good person.

Gauhi, adv., Near; close by.

24 BOGADI—BOGOROGELO

| Bogagapa, n., from gagapa, Extor-
tion; rapaciousness.

Coma, v.t., pft. cumile, hunt ; chase.

Coma, v.i., pft. cumile, be hunted.

Modumod, n., A noise.

Bogamd, Place of milking.

Tlhoko, Wart.

Nna, emph. pron., Ist per., I. v., pft. nntse, sit.

Thuléla, v.t., pft. thuletse. Thuléla.

ENGLISH - SECWANA.

Person, n., Motho.
"""

FREQ = 'gaufi\t10\nmodumo\t5\n'


@pytest.fixture
def data_dir(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    text = tmp_path.joinpath(*TEXT_PATH)
    text.parent.mkdir(parents=True)
    text.write_text(TEXT, encoding='utf-8')
    lexica = tmp_path.joinpath(*LEXICA_PATH)
    lexica.mkdir(parents=True)
    (lexica / FREQ_FILE).write_text(FREQ, encoding='utf-8')
    return tmp_path


def test_modernise():
    assert modernise('Secwana') == 'setswana'
    assert modernise('shupa') == 'supa'
    assert modernise('tsamaea') == 'tsamaya'
    assert modernise('tihogo') == 'tlhogo'


def test_import_brown(data_dir):
    Lexeme.objects.create(setswana='motho', pos='n', english='homo, man', sources=['wordnet'])
    Lexeme.objects.create(setswana='tlhoko', pos='n', english='nipple', sources=['wordnet'])
    Lexeme.objects.create(setswana='tlhoko', pos='v', english='lack', sources=['wordnet'])

    call_command('import_brown')
    call_command('import_brown')

    lexemes = {(lx.setswana, lx.pos): lx for lx in Lexeme.objects.all()}
    assert lexemes['motho', 'n'].english == 'a person; a human being'
    assert lexemes['motho', 'n'].sources == ['wordnet', 'brown']
    assert lexemes['gaufi', 'r'].english == 'near; close by'
    assert lexemes['bogagapa', 'n'].english == 'extortion; rapaciousness'
    assert lexemes['tsoma', 'v'].english == 'hunt; be hunted; chase'
    assert lexemes['modumo', 'n'].english == 'a noise'
    assert lexemes['bogamo', ''].english == 'place of milking'
    assert lexemes['nna', 'pron'].english == 'I'
    assert lexemes['tlhoko', 'n'].english == 'wart'
    assert len(lexemes) == 9
