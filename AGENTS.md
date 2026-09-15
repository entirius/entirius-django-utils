# AGENTS.md

Shared Django utilities for Volkanos services — distribution `entirius-django-utils`, Django app `django_utils`.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_utils` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Default: do not commit — git is the user's call.

## Architecture

Utility library — no concrete models, no migrations (abstract bases only).

- `models/`, `managers/` — abstract base models and manager helpers.
- `api/` — DRF helpers: request parsing decorators (webargs + marshmallow), filters, pagination,
  responses, v1/v2 error handling (`v2_errors.make_exception_handler`, `raise_pydantic_as_drf`).
- `admin/` — admin base classes.
- `tools/` — text/slug helpers (`text`), translation helpers (`t9n`).
- `domains/` — domain helpers (uses `process_logger.ProcessLoggerMixin`).
- `workers/` — management-command base with celery-once locking.
- `json/` — JSON encoder.
- `settings.py` — optional host-project settings with defaults (`MEDIA_URL`, `HEADER_IP_ADDRESS`,
  `HEADER_COUNTRY`, `LOG_HTTP_CODE_GTE`, `ADMIN_THEME`).
- `toolbox/` — AI toolbox client (transport only: no prompts, no models, no Celery):
  `client.py` (`ToolboxClient`: `complete()` single attempt, `list_models()` with retry, `_url(tool, path)`,
  `_get`/`_post`/`_request` for subclasses such as the translator), `errors.py` (typed errors +
  `error_from_response`), `schemas.py` (Pydantic contract), `status.py` (`status()` for UIs),
  `views.py` (`handle_toolbox_error`), `settings.py` (lazy), `testing.py` (respx `mock_toolbox`),
  `outage.py` (dev/test-only outage switch).

## Toolbox client

`docs/toolbox-client.md` is the only reference for the toolbox settings (`AI_TOOLBOX_BASE_URL`,
`AI_TOOLBOX_API_KEY`, `AI_TOOLBOX_CHANNEL`, timeouts, retries), the retry policy, the error mapping
(`ToolboxConnectionError`, `ToolboxBudgetExceededError`, … → `handle_toolbox_error`), `status()` and
`testing.mock_toolbox`. Update it together with any change under `toolbox/`.

## Gotchas

- `django_utils.toolbox.status` is the re-exported function, not the module — patch through the module
  object (`from django_utils.toolbox.status import CACHE_KEY` still works).
- Never log request bodies or the key: the httpx event hook logs method, URL and redacted headers at DEBUG.
- Response-mapped errors carry `default_message` of their class; the toolbox text is on `upstream_message`
  (may quote model output) — never log it, never put it in a response.
