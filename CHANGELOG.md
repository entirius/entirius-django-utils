# Changelog

## 2.1.0 — unreleased

- `django_utils.toolbox`: the AI toolbox client every Volkanos instance carries. `ToolboxClient` with
  `complete(CompletionRequest) -> CompletionResponse` (exactly one HTTP attempt — paid and non-idempotent,
  local validation of tags/temperature/max_tokens before any network call) and `list_models()`
  (plain list, retried with backoff); typed errors (`ToolboxNotConfiguredError`, `ToolboxBudgetExceededError`,
  `ToolboxModelNotAllowedError`, `ToolboxValidationError` with `code` and `field_errors`, …);
  `handle_toolbox_error` for DRF views; `status()` (`configured | unconfigured | unreachable`, cached 60 s);
  `testing.mock_toolbox` respx helper. Moved from `entirius-django-utils-translator`, which now subclasses it.
- New settings, read lazily: `AI_TOOLBOX_BASE_URL`, `AI_TOOLBOX_API_KEY`, `AI_TOOLBOX_CHANNEL`,
  `AI_TOOLBOX_TIMEOUT`, `AI_COMPLETION_TIMEOUT`, `AI_TOOLBOX_MAX_RETRIES`.
- Dependencies: `httpx>=0.27`; `respx>=0.21` in the `test` extra.
- `_post(url, payload, retry=False)` for paid, non-idempotent calls: re-sent only after a connection refusal
  (the request never left) or a 429 with a valid `Retry-After` — never after a timeout, a dropped connection
  or a 5xx. GET calls keep the full retry policy.
- `Retry-After` counts only as a finite number in [0, 300] (`parse_retry_after`); anything else falls back to
  backoff, and `handle_toolbox_error` sets the header only for a valid value.
- Errors mapped from a toolbox response carry a fixed message per class (`str(exc)` adds the upstream `error`
  code); the toolbox's own text is kept on `upstream_message`, never logged or rendered.
- Docs: `docs/toolbox-client.md` — settings, usage, retries, error mapping, status, test helpers.
- `api.v2_errors`: a 409 keeps what the exception carries — its code upper-cased as `error`
  (`Conflict("…", code="already_reviewed")` → `ALREADY_REVIEWED`), its text as `message`, a dict/list detail
  as field `details` (`error: CONFLICT`). Before, every 409 answered `INVALID_REQUEST` / "An error occurred.",
  so clients could not tell conflict kinds apart. Other statuses keep their generic messages.

## 2.0.1 — 2026-09-12

- `api.v2_errors` docs: the usage examples no longer import `standard_exception_handler` from
  `django_contentdb`, which is not a dependency of this package. A service that copied the old
  example without contentdb installed booted fine and then answered every 4xx with a bare 500,
  because DRF resolves `EXCEPTION_HANDLER` lazily at the first error. The examples now show
  `make_exception_handler()` and explain when to pass `v1_handler`. Contributed by
  [@escooterclinic](https://github.com/escooterclinic) (#1).
- Tests for `make_exception_handler`: v1/v2 routing and the no-handler default.
- `.github/CODEOWNERS`: `@entirius/maintainers-backend`.

## 2.0.0 — 2026-07-06

- Initial public release: abstract base models and managers, DRF API helpers (request parsing,
  filtering, pagination, v1/v2 error handling), admin base classes, text and translation tools,
  worker command helpers.
