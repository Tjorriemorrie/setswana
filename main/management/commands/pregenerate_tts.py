import logging

from django.core.management.base import BaseCommand

from main.tts import pregenerate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate (or reuse) TTS clips for the top N ranked lexemes.'

    def add_arguments(self, parser):
        parser.add_argument('--top', type=int, default=300, help='How many ranked lexemes to cover.')

    def handle(self, *args, **options):
        counts = pregenerate(options['top'])
        logger.info('✅ pregenerate_tts finished: top=%s, %s', options['top'], counts)
