"""Numbers for the stats panel: the streak, answers per day, stage counts, due cards and the new-word gate."""

import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from main.models import Card, Review, Settings
from main.srs import recent_accuracy, start_of_day

logger = logging.getLogger(__name__)

# Days shown in the answers-per-day chart, today included.
HISTORY_DAYS = 14


def streak(days, today):
    """Return the number of consecutive practice days ending today, or yesterday if today has none yet."""
    practised = set(days)
    day = today if today in practised else today - timedelta(days=1)
    count = 0
    while day in practised:
        count += 1
        day -= timedelta(days=1)
    return count


def daily_history(now):
    """Return answers, correct answers and accuracy for each of the last HISTORY_DAYS days, oldest first."""
    today = timezone.localtime(now).date()
    rows = (
        Review.objects.filter(created_at__gte=start_of_day(now, 1 - HISTORY_DAYS))
        .annotate(day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()))
        .values('day')
        .annotate(answers=Count('id'), correct=Count('id', filter=Q(correct=True)))
    )
    by_day = {row['day']: row for row in rows}
    peak = max((row['answers'] for row in by_day.values()), default=0)
    history = []
    for offset in range(HISTORY_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        row = by_day.get(day, {'answers': 0, 'correct': 0})
        answers, correct = row['answers'], row['correct']
        history.append(
            {
                'day': day,
                'answers': answers,
                'correct': correct,
                'missed': answers - correct,
                'accuracy': round(100 * correct / answers) if answers else None,
                # Bar heights as percentages of the busiest day.
                'correct_height': round(100 * correct / peak) if peak else 0,
                'missed_height': round(100 * (answers - correct) / peak) if peak else 0,
            }
        )
    logger.info('📊 Daily history: days=%s, active_days=%s, peak=%s', HISTORY_DAYS, len(by_day), peak)
    return history


def panel_stats(now=None):
    """Return everything the stats panel shows."""
    now = now or timezone.now()
    settings = Settings.load()
    today = timezone.localtime(now).date()
    days = (
        Review.objects.annotate(day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()))
        .values_list('day', flat=True)
        .distinct()
    )
    current_streak = streak(days, today)
    logger.info('🔥 Streak: days=%s', current_streak)

    stages = Card.objects.aggregate(
        waiting=Count('id', filter=Q(stage=Card.Stage.NEW, lexeme__rank__isnull=False)),
        learning=Count('id', filter=Q(stage=Card.Stage.LEARNING)),
        consolidating=Count('id', filter=Q(stage=Card.Stage.CONSOLIDATING)),
        long_term=Count('id', filter=Q(stage=Card.Stage.LONG_TERM)),
        listening=Count('id', filter=Q(direction=Card.Direction.AUDIO_TO_TN) & ~Q(stage=Card.Stage.NEW)),
        due_today=Count('id', filter=Q(due__isnull=False, due__lt=start_of_day(now, 1))),
        due_tomorrow=Count('id', filter=Q(due__gte=start_of_day(now, 1), due__lt=start_of_day(now, 2))),
    )
    logger.info('🗂️ Stage and due counts: %s', stages)

    accuracy = recent_accuracy(settings.accuracy_window)
    gate = {
        'pool': stages['learning'],
        'cap': settings.learning_pool_cap,
        'accuracy': round(100 * accuracy),
        'threshold': round(100 * settings.accuracy_threshold),
        'pool_ok': stages['learning'] < settings.learning_pool_cap,
        'accuracy_ok': accuracy >= settings.accuracy_threshold,
        'window': settings.accuracy_window,
    }
    gate['open'] = gate['pool_ok'] and gate['accuracy_ok']

    result = {
        'streak': current_streak,
        'stages': stages,
        'gate': gate,
        'history': daily_history(now),
    }
    logger.info(
        '📊 Panel stats ready: streak=%s, due_today=%s, due_tomorrow=%s, gate_open=%s',
        current_streak,
        stages['due_today'],
        stages['due_tomorrow'],
        gate['open'],
    )
    return result
