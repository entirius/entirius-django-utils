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

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: [AGENTS.md](AGENTS.md).

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
