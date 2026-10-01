import logging

from django.db import models

logger = logging.getLogger(__name__)


def default_consolidation_gaps():
    return [1, 1, 2, 3]


class Lexeme(models.Model):
    setswana = models.CharField(max_length=200, help_text='Headword in modern spelling.')
    english = models.TextField(blank=True)
    pos = models.CharField(max_length=20, blank=True, help_text='Part of speech, e.g. n, v, adj.')
    noun_class = models.CharField(max_length=10, blank=True)
    plural = models.CharField(max_length=200, blank=True)
    frequency = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(
        null=True, blank=True, db_index=True, help_text='Learning order; null = unscheduled.'
    )
    sources = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ('rank', 'setswana')
        constraints = (models.UniqueConstraint(fields=['setswana', 'pos'], name='unique_lexeme_setswana_pos'),)

    def __str__(self):
        return f'{self.setswana} ({self.pos})' if self.pos else self.setswana


class Card(models.Model):
    class Direction(models.TextChoices):
        EN_TO_TN = 'en_to_tn', 'English → Setswana'
        AUDIO_TO_TN = 'audio_to_tn', 'Audio → Setswana'

    class Stage(models.TextChoices):
        NEW = 'new', 'New'
        LEARNING = 'learning', 'Learning'
        CONSOLIDATING = 'consolidating', 'Consolidating'
        LONG_TERM = 'long_term', 'Long-term'

    lexeme = models.ForeignKey(Lexeme, on_delete=models.CASCADE, related_name='cards')
    direction = models.CharField(max_length=20, choices=Direction, default=Direction.EN_TO_TN)
    stage = models.CharField(max_length=20, choices=Stage, default=Stage.NEW, db_index=True)
    consolidation_step = models.PositiveSmallIntegerField(default=0)
    session_correct = models.PositiveSmallIntegerField(default=0)
    due = models.DateTimeField(null=True, blank=True, db_index=True)
    stability = models.FloatField(null=True, blank=True)
    difficulty = models.FloatField(null=True, blank=True)
    reps = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)
    introduced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=['lexeme', 'direction'], name='unique_card_lexeme_direction'),)

    def __str__(self):
        return f'{self.lexeme.setswana} [{self.direction}]'


class Review(models.Model):
    class Rating(models.IntegerChoices):
        AGAIN = 1, 'Again'
        HARD = 2, 'Hard'
        GOOD = 3, 'Good'
        EASY = 4, 'Easy'

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='reviews')
    typed = models.CharField(max_length=200, blank=True)
    correct = models.BooleanField()
    rating = models.PositiveSmallIntegerField(choices=Rating)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.card} {self.get_rating_display()}'


class AudioClip(models.Model):
    text = models.CharField(max_length=500, unique=True)
    path = models.CharField(max_length=255, help_text='Relative to MEDIA_ROOT, e.g. tts/<sha1>.wav.')
    voice = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class Settings(models.Model):
    learning_pool_cap = models.PositiveSmallIntegerField(default=5)
    accuracy_threshold = models.FloatField(default=0.85)
    accuracy_window = models.PositiveSmallIntegerField(default=20)
    session_correct_required = models.PositiveSmallIntegerField(default=3)
    consolidation_gaps = models.JSONField(default=default_consolidation_gaps, help_text='Gaps in days.')
    target_retention = models.FloatField(default=0.90)

    class Meta:
        verbose_name_plural = 'settings'

    def __str__(self):
        return 'Settings'

    @classmethod
    def load(cls):
        """Return the singleton settings row, creating it with defaults if missing."""
        settings, created = cls.objects.get_or_create(pk=1)
        if created:
            logger.info('⚙️ Created default settings row: pk=%s', settings.pk)
        logger.info(
            '⚙️ Loaded settings: pool_cap=%s, accuracy_threshold=%s, accuracy_window=%s',
            settings.learning_pool_cap,
            settings.accuracy_threshold,
            settings.accuracy_window,
        )
        return settings
