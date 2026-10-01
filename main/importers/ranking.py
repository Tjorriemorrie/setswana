"""Build the learning order (`Lexeme.rank`) and the `en_to_tn` cards for ranked lexemes.

Rank = the curated Peace Corps words first, in their curated order, then descending corpus frequency
among the other lexemes with an English gloss. Grammatical particles get no frequency rank: they
belong to the later sentence phase, and their corpus counts would otherwise promote unrelated
homographs (e.g. the concord `ya` over the verb "go").
"""

import logging

from django.db import transaction

from main.models import Card, Lexeme
from main.orthography import strip_diacritics

logger = logging.getLogger(__name__)

# Concords, prepositions, auxiliaries and short demonstratives/relatives.
PARTICLES = frozenset(
    {
        'a', 'ba', 'bo', 'di', 'e', 'eo', 'fa', 'ga', 'go', 'jo', 'joo', 'jwa', 'ka', 'ke', 'ko', 'koo',
        'kwa', 'la', 'le', 'leo', 'lo', 'loo', 'lwa', 'mo', 'moo', 'na', 'ne', 'nne', 'ntse', 'o', 'oo',
        're', 'sa', 'se', 'seo', 'tla', 'tlaa', 'tsa', 'tse', 'tseo', 'wa', 'ya', 'yo', 'yoo',
    }
)  # fmt: skip


@transaction.atomic
def build_ranking():
    """Rank curated, then glossed, attested, non-particle lexemes and sync their cards. Returns a dict of counts."""
    logger.info('🏆 Starting ranking build')
    curated_lexemes = list(Lexeme.objects.filter(curated_order__isnull=False).order_by('curated_order'))
    curated = [lexeme.id for lexeme in curated_lexemes]
    curated_keys = {(strip_diacritics(lexeme.setswana), lexeme.pos) for lexeme in curated_lexemes}
    candidates = list(
        Lexeme.objects.exclude(english='')
        .filter(frequency__gt=0, curated_order__isnull=True)
        .exclude(setswana__in=PARTICLES)
        .order_by('-frequency', 'setswana', 'pos')
        .values_list('id', 'setswana', 'pos')
    )
    # Spelling variants of curated words (ntlo for the curated ntlô) would teach the same word twice.
    by_frequency = [
        lexeme_id for lexeme_id, setswana, pos in candidates if (strip_diacritics(setswana), pos) not in curated_keys
    ]
    ordered = curated + by_frequency
    ranks = {lexeme_id: rank for rank, lexeme_id in enumerate(ordered, start=1)}
    logger.info(
        '🏆 Selected rankable lexemes: curated=%s, by_frequency=%s, curated_variants_skipped=%s',
        len(curated),
        len(by_frequency),
        len(candidates) - len(by_frequency),
    )

    to_update = []
    for lexeme in Lexeme.objects.only('id', 'rank'):
        rank = ranks.get(lexeme.id)
        if lexeme.rank != rank:
            lexeme.rank = rank
            to_update.append(lexeme)
    Lexeme.objects.bulk_update(to_update, ['rank'], batch_size=1000)
    logger.info('🏆 Saved ranks: changed=%s', len(to_update))

    with_card = set(Card.objects.filter(direction=Card.Direction.EN_TO_TN).values_list('lexeme_id', flat=True))
    new_cards = [Card(lexeme_id=lexeme_id, direction=Card.Direction.EN_TO_TN) for lexeme_id in ordered]
    new_cards = [card for card in new_cards if card.lexeme_id not in with_card]
    Card.objects.bulk_create(new_cards, batch_size=1000)
    # Cards of lexemes that lost their rank are dropped, unless they have already been practised.
    removed, _ = Card.objects.filter(lexeme__rank__isnull=True, stage=Card.Stage.NEW, reviews__isnull=True).delete()

    counts = {
        'ranked': len(ranks),
        'curated': len(curated),
        'rank_changes': len(to_update),
        'cards_created': len(new_cards),
        'cards_removed': removed,
    }
    logger.info('✅ Ranking build completed: %s', ', '.join(f'{k}={v}' for k, v in counts.items()))
    return counts
