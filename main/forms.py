"""The settings panel's form: whole-number percentages and the consolidation gaps as a comma list."""

import logging

from django import forms

from main.models import Settings

logger = logging.getLogger(__name__)


class SettingsForm(forms.ModelForm):
    learning_pool_cap = forms.IntegerField(
        min_value=0,
        max_value=50,
        label='Words in learning at once',
        help_text='No new word is introduced while this many are still being learned.',
    )
    accuracy_threshold = forms.IntegerField(
        min_value=0,
        max_value=100,
        label='Accuracy needed for new words',
        help_text='Percent correct on first try. New words wait while you are below it.',
    )
    accuracy_window = forms.IntegerField(
        min_value=1,
        max_value=500,
        label='Answers that count towards accuracy',
        help_text='Accuracy is measured over this many of your latest answers.',
    )
    session_correct_required = forms.IntegerField(
        min_value=1,
        max_value=10,
        label='Correct recalls to finish learning',
        help_text='In a row, in one session. A miss starts the count again.',
    )
    consolidation_gaps = forms.CharField(
        label='Days between consolidation reviews',
        help_text='One number per review, e.g. 1, 1, 2, 3. After the last one the word is known.',
    )
    target_retention = forms.IntegerField(
        min_value=70,
        max_value=99,
        label='Long-term recall target',
        help_text='Percent of known words you should still remember when they come back. Higher means more reviews.',
    )

    class Meta:
        model = Settings
        fields = (
            'learning_pool_cap',
            'accuracy_threshold',
            'accuracy_window',
            'session_correct_required',
            'consolidation_gaps',
            'target_retention',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['accuracy_threshold'] = round(100 * self.instance.accuracy_threshold)
            self.initial['target_retention'] = round(100 * self.instance.target_retention)
            self.initial['consolidation_gaps'] = ', '.join(str(gap) for gap in self.instance.consolidation_gaps)

    def clean_accuracy_threshold(self):
        return self.cleaned_data['accuracy_threshold'] / 100

    def clean_target_retention(self):
        return self.cleaned_data['target_retention'] / 100

    def clean_consolidation_gaps(self):
        raw = self.cleaned_data['consolidation_gaps']
        parts = raw.replace(',', ' ').split()
        if not parts or len(parts) > 10 or not all(part.isdigit() and 1 <= int(part) <= 365 for part in parts):
            logger.warning('⚠️ Rejected consolidation gaps: raw=%r, count=%s', raw, len(parts))
            raise forms.ValidationError('Enter 1 to 10 whole numbers of days (1–365), separated by commas.')
        gaps = [int(part) for part in parts]
        logger.info('⚙️ Parsed consolidation gaps: %s', gaps)
        return gaps
