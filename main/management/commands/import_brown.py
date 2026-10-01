import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from main.importers.brown import import_brown

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import Brown's Secwana Dictionary (OCR text): merge glosses and add new lexemes in modern spelling."

    def add_arguments(self, parser):
        parser.add_argument('--text', type=Path, help='Path to the OCR text (default: under DATA_DIR).')
        parser.add_argument('--freq', type=Path, help='Path to FREQ.LEX.NCHLT.tn.txt (default: under DATA_DIR).')

    def handle(self, *args, **options):
        counts = import_brown(options['text'], options['freq'])
        logger.info(
            '✅ import_brown finished: matched=%s, created=%s, updated=%s',
            counts['matched'],
            counts['created'],
            counts['updated'],
        )
