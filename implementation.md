# Implementation guide

A personal, local-only app for learning Setswana **vocabulary** by typing words from memory, with
adaptive spaced repetition and (later) Setswana TTS. Each numbered step is sized for one fresh
Claude session: start a session with "do step N of implementation.md".

Rules for the project live in `.claude/CLAUDE.md` (scope, frontend, logging, checks). Raw data is
in `data/raw/`, described in `data/SOURCES.md`.

## Progress

- [x] 0. Scope rules, gitignore, this guide
- [x] 1. Models + admin
- [x] 2. Orthography helpers + WordNet importer
- [x] 3. Frequency + ranking
- [x] 4. Brown dictionary importer
- [x] 5. Curated Peace Corps vocabulary
- [x] 6. Scheduler core (learning model)
- [x] 7. Practice UI (single page, htmx)
- [x] 8. TTS v1
- [x] 9. Stats + settings panels
- [ ] 10. Accent improvement (research)
- [ ] Later, only on request: sentence-structure cards

Every step ends with `uv run pre-commit run --all-files` and `uv run pytest` (coverage ≥ 90 %), and
with its box ticked above. Logging follows the global rules: emoji prefix, no DEBUG level.

---

## How the app works

### Data model (`main/models.py`)

| Model | Fields | Notes |
|---|---|---|
| `Lexeme` | `setswana`, `english`, `pos`, `noun_class`, `plural`, `frequency`, `curated_order`, `rank`, `sources` (JSON list), `notes` | Unique on (`setswana`, `pos`). `setswana` is in modern spelling. `curated_order` is the position in the Peace Corps list (null = not curated). `rank` is the learning order (null = not scheduled). |
| `Card` | `lexeme`, `direction`, `stage`, `consolidation_step`, `session_correct`, `due`, `stability`, `difficulty`, `reps`, `lapses`, `introduced_at` | One per (lexeme, direction). Directions: `en_to_tn` (see English, type Setswana) and `audio_to_tn` (hear TTS, type Setswana; enabled in step 8). Stages: `new`, `learning`, `consolidating`, `long_term`. |
| `Review` | `card`, `typed`, `correct`, `rating`, `created_at` | One row per answer, used for accuracy, streaks and stats. |
| `AudioClip` | `text`, `path`, `voice`, `created_at` | The TTS cache index; files live at `media/tts/<sha1>.wav`. |
| `Settings` | `learning_pool_cap` (5), `accuracy_threshold` (0.85), `accuracy_window` (20), `session_correct_required` (3), `consolidation_gaps` ([1, 1, 2, 3]), `target_retention` (0.90) | A singleton row with defaults, editable in the settings panel. |

### Data pipeline (management commands)

The logic lives in `main/importers/<name>.py` and the thin commands in
`main/management/commands/<name>.py`. Every importer is idempotent (it upserts) and logs counts for
each stage.

| Command | Source | What it does |
|---|---|---|
| `import_wordnet` | `data/raw/sadilar/african_wordnet/.../wntsn-lmf.xml` + `data/raw/princeton_wordnet_2.0/WordNet-2.0/dict/data.*` | Each `LexicalEntry` lemma plus its synset id `ENG20-<offset>-<pos>` is looked up in the PWN data file; the first 1–3 synonyms become the English gloss. About 12k lemmas. |
| `import_frequency` | `data/raw/sadilar/nchlt_text/tn/3.Lexica/FREQ.LEX.NCHLT.tn.txt` (`word<TAB>count`) | Sets `Lexeme.frequency`, matching lowercased words. Proper names (capitalised, or in `NELIST.NCHLT.all.txt`) are skipped. |
| `import_brown` | `data/raw/archive_org/brown_1885_secwana_dictionary.txt` | Parses `Headword, pos., gloss` entries from the OCR, converts the old spelling to modern spelling (`main/orthography.py`), and merges into existing lexemes or creates new ones. |
| `import_peace_corps` | `data/curated/peace_corps.yaml` (checked in) | Hand-curated survival vocabulary from Peace Corps lessons 1–23 (plus numbers), matched on diacritic-free spelling. Sets `curated_order` and the curated gloss, which the other importers then leave alone. |
| `build_ranking` | the DB | `rank` = curated Peace Corps words first (by `curated_order`), then descending `frequency` among the other lexemes with an English gloss, skipping spelling variants of curated words (`ntlô` when `ntlo` is curated). Grammatical particles (`go`, `le`, `ya`, `ka`, `mo`, …) get no rank, because they belong to the later sentence phase. Creates the `en_to_tn` cards for ranked lexemes. |

### Learning model: adaptive, no daily cap

New words are gated on how well you're doing, not on a fixed number per day.

1. **Learning (same day, several recalls).** A new word keeps coming back in the session until it
   has been typed correctly `session_correct_required` (3) times, with other cards in between
   (re-insert it after roughly 1, then 5, then 10 cards). A mistake resets that count.
2. **Consolidation (consecutive days).** Next the word is due on following days, with gaps of
   `consolidation_gaps` (1, 1, 2, 3 days). Each due day needs one correct first try to advance. A
   miss sends it back to the first gap.
3. **Long-term.** After that, FSRS (`fsrs` package) schedules growing gaps aimed at
   `target_retention`. A lapse sends the word back to Consolidation.

**Next-card selection:** (a) cards due today, (b) Learning cards whose in-session gap has passed,
(c) a **new word**, but only when the Learning pool is smaller than `learning_pool_cap` **and**
first-try accuracy over the last `accuracy_window` answers is ≥ `accuracy_threshold`. If none of
these applies, the session says you're done for now.

**Grading (automatic):** wrong → Again; correct but with a near-miss typo (edit distance 1, or
missing diacritics) → Hard; correct → Good. A key press can upgrade it to Easy. Answers are
compared after normalising case and whitespace, and accepted without the diacritics ê/ô/š.

### UI: one page, htmx, Bootstrap 5, plain JS

- `/` renders `main/templates/main/index.html`, the only full page. It has three regions:
  - **Counter bar** across the top: introduced / learning / consolidating / known, plus today's
    answers and accuracy.
  - **Practice card** in the centre.
  - **Stats & settings** in a Bootstrap offcanvas, loaded lazily with `hx-get`.
- Partials (in `main/templates/main/partials/`): `card.html`, `feedback.html`, `counters.html`,
  `stats.html`, `settings.html`.
- Flow:
  1. The card loads with `hx-get="/card/"`.
  2. The typed answer goes in with `hx-post="/answer/"`, which returns `feedback.html` (a
     character diff plus TTS audio).
  3. The same response updates `counters.html` with `hx-swap-oob`.
  4. Enter loads the next card.
- All endpoints return HTML partials; there are no JSON endpoints. htmx and Bootstrap are vendored
  in `main/static/vendor/`.
- `main/static/main/app.js` (plain JS) focuses the input, plays the `<audio>` after feedback, and
  handles keyboard shortcuts.

### TTS

- **v1:** UBC-NLP Simba-TTS `UBC-NLP/Simba-TTS-tsn` (a VITS model that runs locally on the CPU) through
  `transformers` + `torch`. Meta's `facebook/mms-tts-tsn`, the original plan, isn't published on Hugging Face.
  `main/tts.py` provides `synthesize(text) -> Path`, cached by text hash in `media/tts/` and indexed in
  `AudioClip`. Files are served from `MEDIA_URL` in DEBUG. `pregenerate_tts --top N` warms the cache.
  Licence is CC BY 4.0.
- **Accent (research):** compare against the native Peace Corps recordings
  (`data/raw/peace_corps/audio/`). Options: a different speaker or voice, or fine-tuning on the
  NCHLT Setswana speech corpus (SADiLaR, not downloaded yet).

---

## Steps

### 1. Models + admin
- **Goal:** the schema above.
- **Files:** `main/models.py`, `main/admin.py`, a migration, `main/tests/test_models.py`.
- **Done when:**
  - migrations apply;
  - all models are registered in the admin (searchable `Lexeme`);
  - `Settings.load()` returns the singleton with defaults;
  - the tests pass.

### 2. Orthography helpers + WordNet importer
- **Goal:** lexemes with English glosses.
- **Files:**
  - `main/orthography.py`: `normalise()` (case, whitespace, NFC) and `strip_diacritics()`;
  - `main/importers/wordnet.py`, `import_wordnet` command;
  - add `DATA_DIR = BASE_DIR / 'data'` to settings.
- **Done when:**
  - there are ≥ 10k lexemes with a non-empty `english`;
  - a spot check of a few common words looks right (`mma`, `ntlo`, `motho`);
  - re-running creates no duplicates.

### 3. Frequency + ranking
- **Goal:** a sensible learning order.
- **Files:** `main/importers/frequency.py`, `main/importers/ranking.py`, the `import_frequency` and
  `build_ranking` commands.
- **Done when:**
  - the top 200 lexemes by rank, printed out, look like useful beginner vocabulary;
  - particles are excluded;
  - `en_to_tn` cards exist for every ranked lexeme.

### 4. Brown dictionary importer
- **Goal:** more and better glosses, especially for verbs and everyday words.
- **Files:**
  - `main/importers/brown.py`: entry parser that handles OCR line wraps and hyphenation, page
    headers, and `v.i.` / `n.` / `adj.`;
  - the old-to-modern spelling rule table in `main/orthography.py`;
  - the `import_brown` command.
- **Done when:**
  - parse stats are logged;
  - the match rate against existing lexemes is reported;
  - new lexemes are added with `sources` containing `brown`;
  - steps 3's commands have been re-run.

### 5. Curated Peace Corps vocabulary
- **Goal:** survival words (greetings, family, numbers, food, directions) first.
- **Files:**
  - `data/curated/peace_corps.yaml`, extracted from `data/raw/peace_corps/bw_setswana_language_lessons.pdf`
    with Claude's help and checked by hand;
  - `main/importers/peace_corps.py`, `import_peace_corps` command;
  - update `build_ranking` so these words come first.
- **Done when:** the first ~150 ranks are the Peace Corps words, in lesson order.
- **Result:** 268 curated words (verbs from lesson 5 make up 83 of them), ranks 1–268. Pipeline order:
  `import_wordnet`, `import_brown`, `import_frequency`, `import_peace_corps`, `build_ranking`; any of them
  can be re-run. Matched lexemes keep their existing spelling (e.g. `gakôlôla`), since other importers
  match on it.

### 6. Scheduler core (learning model)
- **Goal:** the adaptive model above, as pure, testable logic.
- **Files:**
  - `uv add fsrs`;
  - `main/srs.py`: `next_card()`, `grade()`, `submit_answer()`, the new-word gate, the stage
    transitions;
  - `main/answers.py`: `check_answer()` → rating plus diff;
  - tests that simulate several days of answers with frozen time.
- **Done when:**
  - a word goes learning → consolidating → long-term in the simulation;
  - the gate blocks new words when accuracy is below the threshold or the pool is full.
- **Result:** `main/srs.py` + `main/answers.py`, tested with `time-machine`. Decisions:
  - A new word's first showing is an introduction (the UI should show the answer); it moves the card
    to Learning but doesn't count towards `session_correct`.
  - In-session gaps are counted in answered cards (`SESSION_GAPS = (1, 5, 10)`). When there is nothing
    else to do, the Learning card closest to its gap is shown rather than stalling.
  - "Due today" means due before local midnight tonight; consolidation due dates are local midnights.
  - FSRS (learning steps off) is fed only the once-a-day answers from Consolidation onwards, so its
    stability is warm on entering Long-term. Any miss there counts as a lapse.
  - Typos (edit distance 1) are only forgiven in words of ≥ 4 letters (`go` ≠ `ga`).

### 7. Practice UI (single page, htmx)
- **Goal:** daily use in the browser, from the keyboard only.
- **Files:**
  - vendored `main/static/vendor/{htmx.min.js,bootstrap.min.css,bootstrap.bundle.min.js}`;
  - `main/templates/main/index.html` + `partials/`;
  - `main/views.py` (`index`, `card`, `answer`), `config/urls.py`;
  - `main/static/main/app.js`;
  - view tests.
- **Before starting:** invoke the `frontend-design` skill.
- **Done when:**
  - `uv run manage.py runserver` works;
  - you can type answers, see feedback, and have the counters update without a page reload.
- **Result:** "Mafoko" — the page is styled as the Botswana flag (sky-blue field, black band with white
  edges, the card on the band) and follows the system's light or dark mode. Fonts (Bricolage Grotesque for
  English, Atkinson Hyperlegible Mono for Setswana) are vendored in `main/static/vendor/fonts/`, so the app
  works offline, and pre-commit skips `main/static/vendor/`. Decisions:
  - New words are shown with their Setswana; you type it once to introduce it.
  - Easy is chosen when submitting: Shift+Enter instead of Enter. An empty answer counts as a miss.
  - The diff appears for any answer below Good: struck-through letters were typed wrongly, underlined letters were missing.
  - `TIME_ZONE` is still `UTC`, so "today" in the counters and due dates rolls over at UTC midnight.

### 8. TTS v1
- **Goal:** hear every word.
- **Files:**
  - `uv add transformers torch scipy` (CPU);
  - `main/tts.py`, `AudioClip` use, the `pregenerate_tts` command;
  - `MEDIA_ROOT`/`MEDIA_URL` in settings;
  - the play button and auto-play in `feedback.html`;
  - creating `audio_to_tn` cards for words in Consolidation or later.
- **Tests:** mock the model.
- **Done when:**
  - audio plays after each answer;
  - cached files are reused;
  - listening cards appear in sessions.
- **Result:** `main/tts.py` (`synthesize()`, `pregenerate()`), served through `/audio/<lexeme_id>/`, which
  generates the clip on first request and redirects to `MEDIA_URL`, so feedback renders without waiting for
  the model. Decisions:
  - Clips are keyed on the normalised (lowercased) text and generated with a fixed seed, since VITS samples
    durations randomly.
  - The model's vocabulary lacks ê/ô/š and silently drops them, so they are spoken as e/o/sh.
  - A listening card is created when an `en_to_tn` card reaches Consolidation (`build_ranking` backfills any
    missing ones). It enters through the new-word gate, but it isn't an introduction: the answer is hidden and
    the first answer already counts towards `session_correct`.
  - The listening prompt is a strip of the flag's band with a play glyph. Ctrl+Space replays the word on any
    card, and audio auto-plays on listening cards and after every answer.

### 9. Stats + settings panels
- **Goal:** visibility and tuning.
- **Files:** `partials/stats.html` and `partials/settings.html`, loaded into the offcanvas; views for
  each; the settings form posted with `hx-post`.
- **Done when:**
  - the panel shows the streak, answers and accuracy per day, stage counts, and words due tomorrow;
  - changing the gate settings changes how new words are introduced.
- **Result:** `main/stats.py` (`panel_stats()`), `main/forms.py` (`SettingsForm`), and the `/stats/` and `/settings/`
  partials. The offcanvas opens with the top-bar button or Ctrl+. and reloads both partials every time it
  opens. Decisions:
  - The panel's header is a strip of the flag's band carrying the streak: consecutive practice days ending
    today, or yesterday if you haven't practised yet today.
  - A "New words" block shows the gate: open or waiting, with the learning pool against its cap and recent
    accuracy against its threshold, so the effect of a settings change is visible straight away.
  - The 14-day chart is plain HTML/CSS bars (correct in blue, missed in ochre), with no chart library.
  - Percentages are typed as whole numbers and the consolidation gaps as a comma list. Saving sends an
    `HX-Trigger: settings-saved` header, which refreshes the stats.
  - While the panel is open, `app.js` leaves its forms and focus alone. Closing it puts focus back on the card.

### 10. Accent improvement (research)
- **Goal:** TTS that sounds like native Setswana.
- **Work:**
  1. Listen to the Simba-TTS output next to the Peace Corps audio for the same words.
  2. Write up the findings.
  3. Decide between a voice swap, fine-tuning on the NCHLT speech corpus, or keeping v1.
- **Done when:** the decision is recorded here, plus a follow-up step if it's needed.

### Later, only on request: sentence-structure cards
Use the parallel sentences already downloaded (MAFAND, FLORES-200, Tatoeba) and the grammatical
particles excluded in step 3.
