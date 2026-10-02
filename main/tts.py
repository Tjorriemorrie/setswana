"""Setswana text-to-speech with UBC-NLP's Simba-TTS (`UBC-NLP/Simba-TTS-tsn`, a VITS model), cached on disk.

`synthesize(text)` returns the path of a WAV file under `MEDIA_ROOT/tts/`, named by the SHA-1 of the
normalised text and indexed in `AudioClip`, so each text is only ever generated once. The model is
loaded lazily on the first cache miss, because importing torch takes several seconds.
"""

import hashlib
import logging
from functools import cache
from pathlib import Path

from django.conf import settings

from main.models import AudioClip, Lexeme
from main.orthography import normalise, strip_diacritics

logger = logging.getLogger(__name__)

MODEL_ID = 'UBC-NLP/Simba-TTS-tsn'
SEED = 555  # VITS samples its durations randomly; a fixed seed makes regenerated clips identical.


def clip_path(text):
    """Return the clip's path relative to MEDIA_ROOT, e.g. `tts/<sha1>.wav`."""
    return f'tts/{hashlib.sha1(text.encode()).hexdigest()}.wav'  # noqa: S324 - a cache key, not security


@cache
def load_model():
    """Load the TTS model and tokenizer once per process, on the GPU when CUDA is available."""
    import torch
    from transformers import AutoTokenizer, VitsModel

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info('🔊 Loading TTS model: model=%s, device=%s', MODEL_ID, device)
    model = VitsModel.from_pretrained(MODEL_ID).to(device)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    logger.info(
        '🔊 Loaded TTS model: model=%s, device=%s, sampling_rate=%s', MODEL_ID, device, model.config.sampling_rate
    )
    return model, tokenizer


def render(text):
    """Run the model on `text`; return (sampling_rate, float32 samples)."""
    import torch

    model, tokenizer = load_model()
    # The model's vocabulary has no ê/ô/š and silently drops them (dumêla -> dumla).
    speakable = strip_diacritics(text.replace('š', 'sh'))
    inputs = tokenizer(speakable, return_tensors='pt')
    if inputs['input_ids'].shape[-1] == 0:
        logger.error('❌ Text has no characters the TTS model knows: text=%r, model=%s', text, MODEL_ID)
        raise ValueError(f'Nothing to synthesise in {text!r}')
    torch.manual_seed(SEED)  # also seeds CUDA; GPU and CPU still draw different noise, so clips differ slightly
    with torch.no_grad():
        waveform = model(**inputs.to(model.device)).waveform
    samples = waveform.squeeze().cpu().numpy()
    logger.info(
        '🔊 Rendered speech: text=%r, speakable=%r, samples=%s, device=%s', text, speakable, len(samples), model.device
    )
    return model.config.sampling_rate, samples


def synthesize(text):
    """Return the path of a WAV clip of `text`, generating and caching it on the first request."""
    from scipy.io import wavfile

    text = normalise(text)
    relative = clip_path(text)
    path = Path(settings.MEDIA_ROOT) / relative
    if path.exists() and AudioClip.objects.filter(text=text, path=relative).exists():
        logger.info('🔊 TTS cache hit: text=%r, path=%s', text, relative)
        return path
    rate, samples = render(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(path, rate, samples)
    AudioClip.objects.update_or_create(text=text, defaults={'path': relative, 'voice': MODEL_ID})
    logger.info('🔊 TTS clip generated: text=%r, path=%s, rate=%s', text, relative, rate)
    return path


def pregenerate(top):
    """Warm the cache for the `top` ranked lexemes; return counts of generated, cached and failed clips."""
    words = list(Lexeme.objects.filter(rank__isnull=False).order_by('rank').values_list('setswana', flat=True)[:top])
    logger.info('🔊 Starting TTS pregeneration: top=%s, words=%s', top, len(words))
    counts = {'generated': 0, 'cached': 0, 'failed': 0}
    for done, word in enumerate(words, start=1):
        existed = AudioClip.objects.filter(text=normalise(word)).exists()
        try:
            synthesize(word)
        except ValueError:
            counts['failed'] += 1
        else:
            counts['cached' if existed else 'generated'] += 1
        if done % 100 == 0:
            logger.info('🔊 Pregeneration progress: processed=%s, total=%s', done, len(words))
    logger.info(
        '✅ TTS pregeneration completed: total=%s, %s', len(words), ', '.join(f'{k}={v}' for k, v in counts.items())
    )
    return counts
