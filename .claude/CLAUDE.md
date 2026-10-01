# Project instructions

## Keep this file updated

Whenever the user states a preference, convention, or decision about how this project should be
built or how Claude should work in it, add it to this file (in the relevant section, creating one
if needed) in the same turn. Update or remove entries that become outdated so this file always
reflects the user's current preferences.

## Preferences

- Use `uv` for all Python and dependency management (`uv add`, `uv run`); never pip directly.
- Python is pinned to the latest stable release (3.14) via `.python-version`.
- Django project config lives in `config/`; application code goes in the `main` app.
- Linting/formatting is ruff via pre-commit (`uv run pre-commit run --all-files`); rulesets are
  configured in `pyproject.toml`. Code must pass the hooks before committing.
- Logging goes to the console only (no file handlers), configured in `LOGGING` in
  `config/settings.py`. Follow the global logging rules: emoji prefix, no DEBUG level.
