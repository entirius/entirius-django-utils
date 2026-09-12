# Changelog

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
