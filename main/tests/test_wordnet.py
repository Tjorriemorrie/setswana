import pytest
from django.core.management import call_command

from main.importers.wordnet import LMF_PATH, PWN_DICT_PATH
from main.models import Lexeme
from main.orthography import normalise, strip_diacritics

pytestmark = pytest.mark.django_db

LMF = """<?xml version="1.0" encoding="UTF-8"?>
<LexicalResource><Lexicon id="awn_tsn">
  <LexicalEntry id="1"><Lemma writtenForm="mma" partOfSpeech="n"/>
    <Sense id="s1" synset="awn_tsn-ENG20-00000100-n"/>
    <Sense id="s2" synset="awn_tsn-ENG20-00000200-n"/>
  </LexicalEntry>
  <LexicalEntry id="2"><Lemma writtenForm="*ntlo" partOfSpeech="n"/>
    <Sense id="s3" synset="awn_tsn-ENG20-00000200-n"/>
  </LexicalEntry>
  <LexicalEntry id="3"><Lemma writtenForm="ntlo" partOfSpeech="n"/>
    <Sense id="s4" synset="awn_tsn-ENG20-00000100-n"/>
  </LexicalEntry>
  <LexicalEntry id="4"><Lemma writtenForm="James" partOfSpeech="n"/>
    <Sense id="s5" synset="awn_tsn-ENG20-00000100-n"/>
  </LexicalEntry>
  <LexicalEntry id="5"><Lemma writtenForm="dinô tse 40" partOfSpeech="n"/>
    <Sense id="s6" synset="awn_tsn-ENG20-00000100-n"/>
  </LexicalEntry>
  <LexicalEntry id="6"><Lemma writtenForm="kholetshe" partOfSpeech="a"/>
    <Sense id="s7" synset="awn_tsn-64"/>
  </LexicalEntry>
  <LexicalEntry id="7"><Lemma writtenForm="metsi" partOfSpeech="n"/>
    <Sense id="s8" synset="awn_tsn-ENG20-00000100-n"/>
  </LexicalEntry>
</Lexicon></LexicalResource>
"""

DATA_NOUN = """  1 licence header line
00000100 18 n 04 mother 0 female_parent 0 ma 0 mum 0 000 | a female parent
00000200 18 n 01 house 0 000 | a dwelling
"""


@pytest.fixture
def data_dir(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    lmf = tmp_path.joinpath(*LMF_PATH)
    lmf.parent.mkdir(parents=True)
    lmf.write_text(LMF, encoding='utf-8')
    pwn = tmp_path.joinpath(*PWN_DICT_PATH)
    pwn.mkdir(parents=True)
    (pwn / 'data.noun').write_text(DATA_NOUN, encoding='latin-1')
    return tmp_path


def test_orthography():
    assert normalise('  Ntlo\t YA\n rra ') == 'ntlo ya rra'
    assert strip_diacritics('ntšwa ê bopelonôlô') == 'ntswa e bopelonolo'


def test_import_wordnet(data_dir):
    Lexeme.objects.create(setswana='metsi', pos='n', english='water', sources=['brown'])

    call_command('import_wordnet')
    call_command('import_wordnet')

    assert Lexeme.objects.count() == 3
    assert Lexeme.objects.get(setswana='mma').english == 'mother, female parent, ma; house'
    assert Lexeme.objects.get(setswana='ntlo').english == 'house'
    metsi = Lexeme.objects.get(setswana='metsi')
    assert metsi.english == 'water'
    assert metsi.sources == ['brown', 'wordnet']
