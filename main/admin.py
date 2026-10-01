from django.contrib import admin

from main.models import AudioClip, Card, Lexeme, Review, Settings


@admin.register(Lexeme)
class LexemeAdmin(admin.ModelAdmin):
    list_display = ('setswana', 'english', 'pos', 'noun_class', 'frequency', 'rank')
    list_filter = ('pos', 'noun_class')
    search_fields = ('setswana', 'english', 'plural')
    ordering = ('rank', 'setswana')


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('lexeme', 'direction', 'stage', 'due', 'reps', 'lapses')
    list_filter = ('direction', 'stage')
    search_fields = ('lexeme__setswana', 'lexeme__english')
    raw_id_fields = ('lexeme',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('card', 'typed', 'correct', 'rating', 'created_at')
    list_filter = ('correct', 'rating')
    search_fields = ('card__lexeme__setswana', 'typed')
    raw_id_fields = ('card',)


@admin.register(AudioClip)
class AudioClipAdmin(admin.ModelAdmin):
    list_display = ('text', 'voice', 'path', 'created_at')
    search_fields = ('text',)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'learning_pool_cap', 'accuracy_threshold', 'accuracy_window', 'target_retention')
