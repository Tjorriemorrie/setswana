import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from main.importers.peace_corps import import_peace_corps

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import the curated Peace Corps survival vocabulary and mark it for the top ranks.'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=Path, help='Path to peace_corps.yaml (default: under DATA_DIR).')

    def handle(self, *args, **options):
        counts = import_peace_corps(options['path'])
        logger.info(
            '✅ import_peace_corps finished: words=%s, matched=%s, created=%s',
            counts['words'],
            counts['matched'],
            counts['created'],
        )
