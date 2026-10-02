# Project instructions

## Keep this file updated

Whenever the user states a preference, convention, or decision about how this project should be
built or how Claude should work in it, add it to this file (in the relevant section, creating one
if needed) in the same turn. Update or remove entries that become outdated so this file always
reflects the user's current preferences.

## Before finishing any task

Always run both of these when you finish work, fix any failures, and report the results:

1. `uv run pre-commit run --all-files` (ruff check + ruff format + basic hooks)
2. `uv run pytest` (exit code 5 = no tests collected, acceptable only while there is no code to test)

## Scope

- Personal, **local-only, single-user** app for learning Setswana vocabulary by typing + TTS.
- No logins/auth, no accounts, no deployment, no multi-user concerns.
- Local cache files are fine (TTS audio, parsed data, downloads) under `data/cache/` and `media/`
  (both gitignored); raw sources live in `data/raw/` (gitignored, catalogued in `data/SOURCES.md`).
  SQLite is the database.
- Vocabulary only for now; sentence-structure cards come later, only when the user asks.
- Work follows `implementation.md`: one step per session, and tick it off in the checklist when done.

## Frontend

- The whole app is **one page** (`/`). There is no multi-page navigation.
- **Everything after the first page load comes through htmx**: views return HTML partials, and
  forms use `hx-get`/`hx-post`. No JSON APIs for the UI, no full-page reloads.
- CSS framework is **Bootstrap 5** (plus its bundle JS only where a component needs it).
- **Plain JS only**, in small static/inline scripts (keyboard shortcuts, audio playback, focus).
  No JS frameworks, SPAs, bundlers or npm.
- htmx and Bootstrap are vendored into `main/static/vendor/` so the app works offline.

## Preferences

- **Keep it simple and small.** The app is a dictionary plus a voice that pronounces words. Don't add
  heavy ML models, large downloads or research tooling (speech recognition, voice cloning, fine-tuning)
  without asking first, and prefer the smallest dependency that does the job.

- Use `uv` for all Python and dependency management (`uv add`, `uv run`); never pip directly.
- Python is pinned to **3.13 only** (`.python-version` and `requires-python`); do not use 3.14.
- Django project config lives in `config/`; application code goes in the `main` app.
- Linting/formatting is ruff via pre-commit (`uv run pre-commit run --all-files`); rulesets are
  configured in `pyproject.toml`. Code must pass the hooks before committing.
- Tests use pytest + pytest-django (not Django's test runner). Put them in `main/tests/` as
  `test_*.py`; run with `uv run pytest`. Coverage is configured in `pyproject.toml` and the run
  fails below 90%.
- Write the minimum tests and assertions needed to keep coverage at or above 90%. Don't add
  tests or asserts that don't contribute coverage.
- Logging goes to the console only (no file handlers), configured in `LOGGING` in
  `config/settings.py`. Follow the global logging rules: emoji prefix, no DEBUG level.
