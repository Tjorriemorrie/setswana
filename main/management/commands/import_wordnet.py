import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from main.importers.wordnet import import_wordnet

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import Setswana lexemes from the African Wordnet with English glosses from Princeton WordNet 2.0.'

    def add_arguments(self, parser):
        parser.add_argument('--lmf', type=Path, help='Path to wntsn-lmf.xml (default: under DATA_DIR).')
        parser.add_argument('--pwn-dir', type=Path, help='Path to the PWN 2.0 dict/ dir (default: under DATA_DIR).')

    def handle(self, *args, **options):
        counts = import_wordnet(options['lmf'], options['pwn_dir'])
        logger.info('✅ import_wordnet finished: created=%s, updated=%s', counts['created'], counts['updated'])
