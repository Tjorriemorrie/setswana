"""The single practice page and the htmx partials it loads: the next card and the answer feedback."""

import logging

from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from main.models import Card, Lexeme, Review, Settings
from main.srs import next_card, start_of_day, submit_answer
from main.tts import synthesize

logger = logging.getLogger(__name__)


def counters(now):
    """Return the counter bar's numbers: cards per stage plus today's answers and accuracy."""
    stages = Card.objects.aggregate(
        introduced=Count('id', filter=Q(introduced_at__isnull=False)),
        learning=Count('id', filter=Q(stage=Card.Stage.LEARNING)),
        consolidating=Count('id', filter=Q(stage=Card.Stage.CONSOLIDATING)),
        known=Count('id', filter=Q(stage=Card.Stage.LONG_TERM)),
    )
    today = Review.objects.filter(created_at__gte=start_of_day(now)).aggregate(
        answers=Count('id'), correct=Count('id', filter=Q(correct=True))
    )
    accuracy = round(100 * today['correct'] / today['answers']) if today['answers'] else None
    result = {**stages, 'answers': today['answers'], 'accuracy': accuracy}
    logger.info('🧮 Counters: %s', result)
    return result


@require_GET
def index(request):
    """Render the practice page; the card itself is loaded with htmx."""
    context = {'counters': counters(timezone.now())}
    logger.info('🏠 Rendering practice page')
    return render(request, 'main/index.html', context)


@require_GET
def card(request):
    """Render the next card to practise, or the done-for-now message."""
    now = timezone.now()
    chosen = next_card(now)
    context = {'card': chosen}
    if chosen is None:
        upcoming = Card.objects.filter(due__isnull=False, due__gt=now).order_by('due').first()
        context['next_due'] = upcoming.due if upcoming else None
        logger.info('🏁 Rendering done card: next_due=%s', context['next_due'])
    else:
        context['listen'] = chosen.direction == Card.Direction.AUDIO_TO_TN
        # Listening cards are for words already learned by sight, so they are never introduced.
        context['introduce'] = chosen.stage == Card.Stage.NEW and not context['listen']
        logger.info(
            '🃏 Rendering card: card=%s, stage=%s, introduce=%s, listen=%s',
            chosen,
            chosen.stage,
            context['introduce'],
            context['listen'],
        )
    return render(request, 'main/partials/card.html', context)


@require_POST
def answer(request):
    """Grade a typed answer and render the feedback, updating the counters out of band."""
    chosen = get_object_or_404(Card.objects.select_related('lexeme'), pk=request.POST.get('card'))
    introduced = chosen.stage == Card.Stage.NEW and chosen.direction == Card.Direction.EN_TO_TN
    typed = request.POST.get('typed', '')
    easy = request.POST.get('easy') == '1'
    result = submit_answer(chosen, typed, easy=easy)
    context = {
        'card': chosen,
        'result': result,
        'typed': typed.strip(),
        'introduced': introduced,
        'rating': Review.Rating(result.rating).label,
        'required': Settings.load().session_correct_required,
        'counters': counters(timezone.now()),
    }
    logger.info(
        '📨 Rendering feedback: card=%s, typed=%r, rating=%s, introduced=%s',
        chosen,
        typed,
        context['rating'],
        introduced,
    )
    return render(request, 'main/partials/feedback.html', context)


@require_GET
def audio(request, lexeme_id):
    """Redirect to the lexeme's TTS clip, generating it on first request."""
    lexeme = get_object_or_404(Lexeme, pk=lexeme_id)
    try:
        path = synthesize(lexeme.setswana)
    except ValueError as exc:
        logger.warning('⚠️ No audio for lexeme: lexeme_id=%s, setswana=%r, error=%s', lexeme_id, lexeme.setswana, exc)
        raise Http404('No audio for this word') from exc
    url = f'{settings.MEDIA_URL}{path.relative_to(settings.MEDIA_ROOT).as_posix()}'
    logger.info('🔊 Serving audio: lexeme_id=%s, setswana=%r, url=%s', lexeme_id, lexeme.setswana, url)
    return redirect(url)
