# entirius-django-utils

Shared Django building blocks for the modules of Entirius, the open-source modular ecommerce platform.
Abstract base models, DRF API helpers, admin base classes, text tools and an AI toolbox client live here, so
every module builds on the same foundations.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-utils.svg)](https://pypi.org/project/entirius-django-utils/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-utils.svg)](https://pypi.org/project/entirius-django-utils/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-utils/blob/develop/LICENSE)

## What it does

- Abstract base models and manager helpers shared by every Entirius module.
- DRF helpers: request parsing, filtering, pagination and the structured v2 error handling.
- Admin base classes, text, slug and translation helpers.
- A base for worker management commands with locking.
- A typed client for the AI toolbox (completions, model catalogue, error mapping to DRF responses).

## Installation

```shell
uv add entirius-django-utils
pip install entirius-django-utils
```

Optional extra: `entirius-django-utils[unfold]` (django-unfold admin theme).

```python
INSTALLED_APPS = [
    ...
    "django_regional",
    "django_utils",
]
```

The toolbox client needs `AI_TOOLBOX_BASE_URL`, `AI_TOOLBOX_API_KEY` and `AI_TOOLBOX_CHANNEL`; the settings
reference is https://github.com/entirius/entirius-django-utils/blob/develop/docs/toolbox-client.md.

## Quick start

```python
from django_utils.toolbox import CompletionRequest, Message, ToolboxClient

# settings: AI_TOOLBOX_BASE_URL = "https://toolbox.example.com"
with ToolboxClient() as client:
    response = client.complete(
        CompletionRequest(
            model="fake-chat",
            messages=[Message(role="user", content="Say hi as JSON")],
            json_schema={"type": "object"},
        )
    )
```

## Requirements

- Python 3.11 or newer, Django 4.2 or newer.
- Entirius packages pulled in: `entirius-django-regional`, `entirius-py-idx-normalizator`,
  `entirius-py-process-logger`.

## Documentation

- Module docs: https://github.com/entirius/entirius-django-utils/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-utils/blob/develop/CHANGELOG.md

## Part of Entirius

Every module of the Entirius backend service (Volkanos) depends on this package.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-regional, https://github.com/entirius/entirius-django-utils-translator

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: https://github.com/entirius/entirius-django-utils/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-utils/blob/develop/LICENSE.
