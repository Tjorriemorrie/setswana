import logging

from django.core.management.base import BaseCommand

from main.importers.ranking import build_ranking
from main.models import Lexeme

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rank lexemes into a learning order and create en_to_tn cards for ranked lexemes.'

    def add_arguments(self, parser):
        parser.add_argument('--show', type=int, default=0, help='Print the top N ranked lexemes.')

    def handle(self, *args, **options):
        counts = build_ranking()
        for lexeme in Lexeme.objects.filter(rank__isnull=False)[: options['show']]:
            self.stdout.write(
                f'{lexeme.rank:>5}  {lexeme.setswana:<20} {lexeme.pos:<3} {lexeme.frequency:>6}  {lexeme.english}'
            )
        logger.info('✅ build_ranking finished: ranked=%s, cards_created=%s', counts['ranked'], counts['cards_created'])
