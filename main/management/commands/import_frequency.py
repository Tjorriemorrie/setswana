import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from main.importers.frequency import import_frequency

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Set lexeme frequencies from the NCHLT Setswana corpus frequency list.'

    def add_arguments(self, parser):
        parser.add_argument('--freq', type=Path, help='Path to FREQ.LEX.NCHLT.tn.txt (default: under DATA_DIR).')
        parser.add_argument('--ne', type=Path, help='Path to NELIST.NCHLT.all.txt (default: under DATA_DIR).')

    def handle(self, *args, **options):
        counts = import_frequency(options['freq'], options['ne'])
        logger.info('✅ import_frequency finished: matched=%s, updated=%s', counts['matched'], counts['updated'])
