# django-utils

Shared Django utilities for Volkanos services — abstract base models and managers, DRF API helpers
(request parsing, filtering, pagination, v1/v2 error handling), admin base classes, text and
translation tools, and worker command helpers.

## Installation

```shell
pip install entirius-django-utils
```

Add the app to your project:

```python
INSTALLED_APPS = [
    ...
    "django_utils",
]
```

## Toolbox client

`django_utils.toolbox` talks to the Entirius AI Toolbox (completion proxy + model catalogue). Configure it in
the service settings; with any of the three empty, the client raises `ToolboxNotConfiguredError` and
`status()` returns `unconfigured` without touching the network.

```python
AI_TOOLBOX_BASE_URL = "https://ai-toolbox.internal:8000"
AI_TOOLBOX_API_KEY = env("AI_TOOLBOX_API_KEY")
AI_TOOLBOX_CHANNEL = "my-channel"
```

```python
from django_utils.toolbox import CompletionRequest, Message, ToolboxClient, ToolboxError, handle_toolbox_error

try:
    with ToolboxClient() as client:
        response = client.complete(
            CompletionRequest(
                model="fake-chat",
                messages=[Message(role="user", content="Say hi as JSON")],
                json_schema={"type": "object"},
                tags=["leads.draft"],
            )
        )
except ToolboxError as exc:
    return handle_toolbox_error(exc)  # DRF Response: 402/403/404/400/422/503/504 or a generic 502
```

`complete()` makes exactly one HTTP attempt — it is paid and non-idempotent, retrying is the caller's
decision. `list_models()` retries on 5xx with backoff. Store responses with `model_dump(mode="json")`
(`cost` is a `Decimal`). In tests, `django_utils.toolbox.testing.mock_toolbox()` (needs the `test` extra)
mocks both endpoints with canned answers; `error_response(402, "BUDGET_EXCEEDED")` builds error bodies.

Full reference — settings, retries, error mapping: [docs/toolbox-client.md](docs/toolbox-client.md).

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: [AGENTS.md](AGENTS.md).

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
