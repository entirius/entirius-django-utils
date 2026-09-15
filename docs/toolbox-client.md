---
title: AI toolbox client
description: django_utils.toolbox — settings, ToolboxClient usage, retries, typed errors, DRF mapping, status probe, test helpers.
---

`django_utils.toolbox` is the HTTP client every Volkanos module uses to reach the Entirius AI Toolbox
(completion proxy + model catalogue). Transport only: it sends requests, maps failures to typed exceptions
and returns parsed bodies. Prompts, models and Celery tasks belong to the calling module.

## Settings

Read from `django.conf.settings` on every access, so `override_settings` works. With any of the first three
empty the instance runs without the toolbox: `ToolboxClient()` raises `ToolboxNotConfiguredError` and
`status()` returns `unconfigured` without a network call.

| Setting | Default | Meaning |
|---|---|---|
| `AI_TOOLBOX_BASE_URL` | `""` | toolbox root URL (trailing `/` is stripped) |
| `AI_TOOLBOX_API_KEY` | `""` | sent as `X-API-Key` — a secret, keep it out of the repository |
| `AI_TOOLBOX_CHANNEL` | `""` | toolbox channel idx, part of every URL; `[a-zA-Z0-9_-]+`, else `ValueError` |
| `AI_TOOLBOX_TIMEOUT` | `60.0` | seconds, `list_models()` and subclass calls |
| `AI_COMPLETION_TIMEOUT` | `130.0` | seconds, `complete()` — above the toolbox's 120 s cap, so an upstream timeout arrives as a typed 504 |
| `AI_TOOLBOX_MAX_RETRIES` | `3` | attempts in total for retriable calls; never applies to `complete()` |

```python
# service settings_local.py
AI_TOOLBOX_BASE_URL = "https://ai-toolbox.internal:8000"
AI_TOOLBOX_API_KEY = env("AI_TOOLBOX_API_KEY")
AI_TOOLBOX_CHANNEL = "my-channel"
```

Dependencies: `httpx` and `pydantic` at runtime; `respx` only for `django_utils.toolbox.testing`
(the `test` extra).

## Usage

```python
from django_utils.toolbox import CompletionRequest, Message, ToolboxClient, ToolboxError, handle_toolbox_error

try:
    with ToolboxClient() as client:            # or ToolboxClient("other-channel", max_retries=1)
        response = client.complete(
            CompletionRequest(
                model="fake-chat",
                messages=[Message(role="user", content="Say hi as JSON")],
                json_schema={"type": "object"},
                tags=["leads.draft"],
            )
        )
except ToolboxError as exc:
    return handle_toolbox_error(exc)
```

| Method | HTTP | Returns | Attempts |
|---|---|---|---|
| `complete(CompletionRequest)` | `POST {base}/api/ai-completion/v2/admin/{channel}/complete/` | `CompletionResponse` (`output`, `parsed`, `usage`, `cost`, `model`, `attempts`, `request_id`) | exactly one |
| `list_models(timeout=None)` | `GET …/models/` | `list[ModelInfo]` — the models this channel may use | up to `AI_TOOLBOX_MAX_RETRIES` |

- `complete()` re-validates the request locally before any network call (`messages` ≥ 1, `temperature`
  0–2, `max_tokens` 1–8192, ≤ 10 `tags` matching `^[a-z0-9_.:-]{1,64}$`); a violation raises
  `ToolboxValidationError(400, code="VALIDATION_ERROR")` with `field_errors`.
- A 2xx body that does not match the schema raises `ToolboxServerError(200)`, never a raw pydantic error.
- Store responses with `model_dump(mode="json")` — `cost` and prices are `Decimal`.
- Use the client as a context manager (or call `close()`): it owns an `httpx.Client`.
- Subclasses (the translator client) build URLs with `_url(tool, path)` and call `_get` / `_post`.

## Retries

| Call | Retried on | Backoff |
|---|---|---|
| `complete()` | never | — |
| `_get`, `_post(retry=True)` | 408, 429, 500, 502, 503, 504, timeouts, transport errors | 2 s × 2ⁿ, max 60 s |
| `_post(retry=False)` — paid, non-idempotent | a connection refusal (the request never left) or a 429 with a valid `Retry-After` | as above |

A 429 with `Retry-After` waits that many seconds (capped at 60). `Retry-After` counts only as a finite
number in [0, 300] (`parse_retry_after`); anything else falls back to backoff. The toolbox has no
`Idempotency-Key`, so a paid POST is never re-sent after a timeout, a dropped connection or a 5xx.

## Errors

All inherit `ToolboxError` (`status_code`, `message`, `code`, `field_errors`, `upstream_message`).
`status_code` is `0` for failures without an HTTP response.

| Toolbox response | Exception | `handle_toolbox_error` response |
|---|---|---|
| a setting is empty | `ToolboxNotConfiguredError` | 503 `AI_TOOLBOX_NOT_CONFIGURED` |
| 402 | `ToolboxBudgetExceededError` | 402 `BUDGET_EXCEEDED` |
| 403 `MODEL_NOT_ALLOWED` | `ToolboxModelNotAllowedError` | 403 `MODEL_NOT_ALLOWED` |
| 401 / other 403 | `ToolboxAuthError` | 502 `PROVIDER_ERROR` + `debug_id` |
| 404 | `ToolboxNotFoundError` | 404 `NOT_FOUND` |
| 400 / 422 | `ToolboxValidationError` | same status, `code`, `field_errors` |
| 429 | `ToolboxRateLimitError` (`retry_after`) | 429 `RATE_LIMIT_EXCEEDED` (+ `Retry-After` when valid) |
| 503 `UPSTREAM_RATE_LIMITED` | `ToolboxRateLimitError` | 503 `UPSTREAM_RATE_LIMITED` |
| 504 / client timeout | `ToolboxTimeoutError` | 504 `UPSTREAM_TIMEOUT` |
| DNS failure, connection refused, protocol error | `ToolboxConnectionError` | 502 `PROVIDER_ERROR` + `debug_id` |
| other 5xx, non-JSON body | `ToolboxServerError` | 502 `PROVIDER_ERROR` + `debug_id` |

`handle_toolbox_error` returns a DRF `Response` with `{"error", "message", …}`. For the 502 cases it logs
the exception type, status and code with the `debug_id` — never the prompt, the key or the toolbox text.

`message` on a response-mapped error is the class's fixed `default_message`; `str(exc)` adds the upstream
`error` code. The toolbox's own text is kept on `upstream_message` — it may quote model output, so never log
it and never put it into a response.

## Status for UIs

`status()` returns `ToolboxStatus.configured | unconfigured | unreachable` and never raises, so it is safe
inside a request. `unconfigured` needs no network; otherwise one `GET models/` probe (single attempt, 5 s
timeout) is cached for 60 s under `django_utils.toolbox.status` in the Django cache. A failing cache backend
reads as `unreachable`.

The attribute `django_utils.toolbox.status` is the re-exported function, not the module: a dotted
`monkeypatch.setattr("django_utils.toolbox.status.<name>", …)` resolves to the function. Patch the module
object from `sys.modules` (or `importlib.import_module`) instead; `from django_utils.toolbox.status import
CACHE_KEY` still works.

## Logging

- Importing the client sets the `httpx` logger to `WARNING`, process-wide, so request lines never reach
  service logs.
- The client's own request hook logs method, URL and headers with `X-API-Key` redacted at `DEBUG` — never
  the body. Retries log one `WARNING` with the attempt, the exception type and the delay.

## Testing a consumer

```python
from django_utils.toolbox.testing import error_response, mock_toolbox

def test_budget(settings):
    settings.AI_TOOLBOX_BASE_URL = "http://toolbox.test"
    settings.AI_TOOLBOX_API_KEY = "test-key"
    settings.AI_TOOLBOX_CHANNEL = "test"
    with mock_toolbox() as router:
        router["complete"].mock(return_value=error_response(402, "BUDGET_EXCEEDED"))
        ...
```

`mock_toolbox()` mocks the configured base URL and channel: route `complete` answers `CANNED_COMPLETION`,
route `models` answers `CANNED_MODELS` (one `fake-chat` model). Unused routes do not fail the test.
The suite of this package: `tests/toolbox/` (`test_client`, `test_views`, `test_status`, `test_logging`).
