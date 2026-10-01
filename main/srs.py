"""The adaptive learning model: next-card selection, the new-word gate and the stage transitions.

Learning happens within a session (in-session gaps counted in answered cards), Consolidation over
consecutive days (`Settings.consolidation_gaps`), and Long-term is scheduled by FSRS. FSRS sees only
the once-a-day answers from Consolidation onwards, so its own learning steps are switched off.
"""

import logging
from datetime import datetime, time, timedelta

import fsrs
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from main.answers import check_answer
from main.models import Card, Review, Settings

logger = logging.getLogger(__name__)

# Answered cards needed between two showings of a Learning card, indexed by its session_correct.
SESSION_GAPS = (1, 5, 10)


def start_of_day(now, days=0):
    """Return local midnight of the day `days` after the day of `now`."""
    day = timezone.localtime(now).date() + timedelta(days=days)
    return timezone.make_aware(datetime.combine(day, time.min))


def recent_accuracy(window):
    """Return the share of correct answers among the last `window` answers (1.0 when there are none)."""
    results = list(Review.objects.order_by('-created_at', '-id').values_list('correct', flat=True)[:window])
    accuracy = sum(results) / len(results) if results else 1.0
    logger.info('🎯 Recent accuracy: answers=%s, window=%s, accuracy=%.2f', len(results), window, accuracy)
    return accuracy


def can_introduce(settings):
    """Return whether a new word may be introduced: the pool has room and accuracy is high enough."""
    pool = Card.objects.filter(stage=Card.Stage.LEARNING).count()
    accuracy = recent_accuracy(settings.accuracy_window)
    allowed = pool < settings.learning_pool_cap and accuracy >= settings.accuracy_threshold
    logger.info(
        '🚦 New-word gate: allowed=%s, pool=%s, cap=%s, accuracy=%.2f, threshold=%s',
        allowed,
        pool,
        settings.learning_pool_cap,
        accuracy,
        settings.accuracy_threshold,
    )
    return allowed


def learning_candidates():
    """Return Learning cards as (cards_answered_since, needed_gap, card), the most overdue first."""
    cards = Card.objects.filter(stage=Card.Stage.LEARNING).annotate(last_review_id=Max('reviews__id'))
    candidates = []
    for card in cards:
        since = Review.objects.filter(id__gt=card.last_review_id or 0).count()
        gap = SESSION_GAPS[min(card.session_correct, len(SESSION_GAPS) - 1)]
        candidates.append((since, gap, card))
    candidates.sort(key=lambda c: (c[0] - c[1], c[0]), reverse=True)
    logger.info('🔁 Learning candidates: pool=%s, ready=%s', len(candidates), sum(s >= g for s, g, _ in candidates))
    return candidates


def next_card(now=None):
    """Return the next card to practise, or None when there is nothing to do for now."""
    now = now or timezone.now()
    settings = Settings.load()
    due = (
        Card.objects.filter(stage__in=(Card.Stage.CONSOLIDATING, Card.Stage.LONG_TERM), due__lt=start_of_day(now, 1))
        .order_by('due', 'id')
        .first()
    )
    if due:
        logger.info('📅 Next card is due: card=%s, stage=%s, due=%s', due, due.stage, due.due)
        return due
    candidates = learning_candidates()
    ready = [card for since, gap, card in candidates if since >= gap]
    if ready:
        logger.info('🔁 Next card is a learning card: card=%s, session_correct=%s', ready[0], ready[0].session_correct)
        return ready[0]
    if can_introduce(settings):
        new = (
            Card.objects.filter(stage=Card.Stage.NEW, lexeme__rank__isnull=False)
            .order_by('lexeme__rank', 'direction')
            .first()
        )
        if new:
            logger.info('🆕 Next card is a new word: card=%s, rank=%s', new, new.lexeme.rank)
            return new
        logger.info('🆕 No new words left to introduce')
    if candidates:
        # Nothing else to do: rather than stall, show the Learning card closest to its gap.
        card = candidates[0][2]
        logger.info('🔁 Next card is a learning card before its gap: card=%s, pool=%s', card, len(candidates))
        return card
    logger.info('🏁 Nothing to practise for now')
    return None


def fsrs_scheduler(settings):
    """Return an FSRS scheduler with learning steps off, since the stages before Long-term handle those."""
    return fsrs.Scheduler(desired_retention=settings.target_retention, learning_steps=(), relearning_steps=())


def review_fsrs(card, rating, now, settings):
    """Feed a daily answer to FSRS, storing stability and difficulty; return the FSRS due date."""
    if card.stability is None:
        memory = fsrs.Card()
    else:
        previous = card.reviews.filter(created_at__lt=now).order_by('-created_at', '-id').first()
        memory = fsrs.Card(
            state=fsrs.State.Review,
            stability=card.stability,
            difficulty=card.difficulty,
            due=card.due or now,
            last_review=previous.created_at if previous else now,
        )
    memory, _ = fsrs_scheduler(settings).review_card(memory, fsrs.Rating(rating), review_datetime=now)
    card.stability, card.difficulty = memory.stability, memory.difficulty
    logger.info(
        '🧠 FSRS review: card=%s, rating=%s, stability=%.2f, difficulty=%.2f, due=%s',
        card,
        rating,
        memory.stability,
        memory.difficulty,
        memory.due,
    )
    return memory.due


def grade(card, rating, now, settings):
    """Apply an answer's rating to the card's stage, counters and due date (the card is not saved)."""
    correct = rating != Review.Rating.AGAIN
    before = card.stage
    card.reps += 1
    if card.stage == Card.Stage.NEW:
        # The first showing introduces the word; recall only counts from the next showing. A listening
        # card's word is already known by sight, so its first answer is a real recall.
        listening = card.direction == Card.Direction.AUDIO_TO_TN
        card.stage, card.introduced_at = Card.Stage.LEARNING, now
        card.session_correct = int(listening and correct)
    elif card.stage == Card.Stage.LEARNING:
        card.session_correct = card.session_correct + 1 if correct else 0
        if card.session_correct >= settings.session_correct_required:
            card.stage, card.consolidation_step = Card.Stage.CONSOLIDATING, 0
            card.due = start_of_day(now, settings.consolidation_gaps[0])
    else:
        fsrs_due = review_fsrs(card, rating, now, settings)
        if not correct:
            card.lapses += 1
            card.stage, card.consolidation_step = Card.Stage.CONSOLIDATING, 0
            card.due = start_of_day(now, settings.consolidation_gaps[0])
        elif card.stage == Card.Stage.CONSOLIDATING:
            card.consolidation_step += 1
            if card.consolidation_step >= len(settings.consolidation_gaps):
                card.stage, card.due = Card.Stage.LONG_TERM, fsrs_due
            else:
                card.due = start_of_day(now, settings.consolidation_gaps[card.consolidation_step])
        else:
            card.due = fsrs_due
    logger.info(
        '📈 Graded card: card=%s, rating=%s, stage=%s→%s, session_correct=%s, step=%s, due=%s',
        card,
        rating,
        before,
        card.stage,
        card.session_correct,
        card.consolidation_step,
        card.due,
    )
    return card


def submit_answer(card, typed, easy=False, now=None):
    """Check a typed answer, update the card's schedule and record the review; return the check."""
    now = now or timezone.now()
    settings = Settings.load()
    result = check_answer(typed, card.lexeme.setswana, easy=easy)
    with transaction.atomic():
        grade(card, result.rating, now, settings)
        card.save()
        Review.objects.create(card=card, typed=typed, correct=result.correct, rating=result.rating)
        if card.direction == Card.Direction.EN_TO_TN and card.stage in (Card.Stage.CONSOLIDATING, Card.Stage.LONG_TERM):
            _, created = Card.objects.get_or_create(lexeme=card.lexeme, direction=Card.Direction.AUDIO_TO_TN)
            if created:
                logger.info('🎧 Created listening card: lexeme=%s', card.lexeme)
    logger.info(
        '✅ Answer submitted: card=%s, correct=%s, rating=%s, stage=%s', card, result.correct, result.rating, card.stage
    )
    return result
