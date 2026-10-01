import pytest
from django.core.management import call_command

from main.importers.peace_corps import YAML_PATH, import_peace_corps
from main.models import Lexeme

pytestmark = pytest.mark.django_db

YAML = """lessons:
  - lesson: 2
    title: Greetings
    words:
      - {setswana: dumêla, pos: interj, english: "hello"}
      - {setswana: sentle, pos: r, english: "well"}
  - lesson: 18
    title: Places
    words:
      - {setswana: ntlô, pos: n, english: "house"}
      - {setswana: ngwana, pos: n, english: "child", plural: bana}
"""


@pytest.fixture
def yaml_path(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    path = tmp_path.joinpath(*YAML_PATH)
    path.parent.mkdir(parents=True)
    path.write_text(YAML, encoding='utf-8')
    return path


def test_import_peace_corps(yaml_path):
    Lexeme.objects.create(setswana='ntlô', pos='n', english='dwelling', sources=['wordnet'])
    Lexeme.objects.create(setswana='ntlo', pos='n', english='home', frequency=100, sources=['wordnet'])
    Lexeme.objects.create(setswana='sentle', pos='a', english='pretty', frequency=50, sources=['brown'])
    Lexeme.objects.create(setswana='motho', pos='n', english='person', frequency=80)
    Lexeme.objects.create(
        setswana='pula', pos='n', english='rain', frequency=10, curated_order=1, sources=['peace_corps']
    )

    call_command('import_peace_corps')
    call_command('import_peace_corps')
    call_command('build_ranking')

    ranked = Lexeme.objects.filter(rank__isnull=False).order_by('rank')
    assert [(lx.setswana, lx.pos, lx.english) for lx in ranked] == [
        ('dumêla', 'interj', 'hello'),
        ('sentle', 'a', 'well'),
        ('ntlô', 'n', 'house'),
        ('ngwana', 'n', 'child'),
        ('motho', 'n', 'person'),
        ('pula', 'n', 'rain'),
    ]
    assert Lexeme.objects.get(setswana='ngwana').plural == 'bana'
    assert Lexeme.objects.get(setswana='pula').sources == []


def test_duplicate_word(yaml_path):
    yaml_path.write_text(YAML + '      - {setswana: ntlo, pos: n, english: "home"}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        import_peace_corps()
