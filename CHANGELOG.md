# Changelog

## 2.4.2 — 2026-10-29

### Security

- `get_client_ip` supports a storefront that proxies `/api/*` server-side (Next rewrite): all such traffic arrives
  from the storefront's IP, so per-IP throttles collapsed into one bucket per shop. New settings (both default to
  the 2.4.1 behaviour): `CLIENT_IP_TRUSTED_PROXIES` (IPs or CIDRs, default empty) and `CLIENT_IP_FORWARDED_HEADER`
  (`request.META` key, default `HTTP_X_CLIENT_IP`). When the edge IP (from `CLIENT_IP_HEADER` or DRF `get_ident`) is
  inside a trusted proxy, the visitor IP is read from the forwarded header, if it is a valid IP address; otherwise
  the edge IP is used. The storefront must always overwrite that header. A malformed trusted-proxy entry raises
  `ImproperlyConfigured`; the list is parsed once (cached per distinct setting value), not per request. IPv4-mapped
  IPv6 addresses (`::ffff:1.2.3.4`) are normalised to IPv4 before matching, for the edge IP and the forwarded value.

## 2.4.1 — 2026-10-29

### Security

- New `django_utils.api.client_ip`: `get_client_ip(request)` and `ClientIPThrottleMixin` for DRF throttles. New
  setting `CLIENT_IP_HEADER` (a `request.META` key, e.g. `HTTP_CF_CONNECTING_IP`; default unset): when set and present
  it is the client IP, otherwise DRF's `get_ident` applies (`NUM_PROXIES`). Per-IP throttles keyed on
  `X-Forwarded-For` can be bypassed by spoofing it; set the header only when the origin is reachable solely through
  the proxy that sets it.
- `verify_captcha` logs a warning per decorated view when `django_captcha` is not installed (was silent). New setting
  `CAPTCHA_REQUIRED` (default `False`, behaviour unchanged): `True` raises `ImproperlyConfigured` at decoration time
  when `django_captcha` is missing or not in `INSTALLED_APPS`.

## 2.4.0 — 2026-10-27

2.3.1rc1 was never published; its fix ships here.

- `django_utils.api.v2_errors`: Django's `Http404` (raised by `get_object_or_404`) answers `error: NOT_FOUND` like
  DRF's `NotFound`; before, the v2 envelope said `INVALID_REQUEST` on a 404.
- `django_utils.api.v2_errors`: `raise_pydantic_as_drf(exc, location="body")` takes the location of the validated
  input (`body` | `path` | `query`) and the v2 handler puts it on every detail; a schema built from
  `request.query_params` passes `"query"` (#12). Before, every detail said `body`. Modules update their query-schema
  calls at their next release.

## 2.3.0 — 2026-10-12

- `django_utils.toolbox`: new setting `AI_TOOLBOX_ENABLED` (default `True`). `False` switches the AI toolbox off on
  purpose: `ToolboxClient()` raises the new `ToolboxDisabledError` (code `AI_TOOLBOX_DISABLED`) before the
  not-configured check, `status()` returns the new `ToolboxStatus.DISABLED` (`disabled`) without network or cache,
  and `handle_toolbox_error` answers 503 `AI_TOOLBOX_DISABLED`. New `is_enabled()`. The outage switch has no effect
  while the toolbox is disabled. Nothing changes for an instance that leaves the setting alone.
- Optional sibling apps that are installed but not enabled no longer crash imports (`RuntimeError` is caught like
  `ImportError`).

### Security

- `verify_captcha` logs one warning per decorated view, at import time, when `django_captcha` is installed but not
  in `INSTALLED_APPS`: the view still runs without captcha (unchanged), and the log names it, so an app dropped by
  mistake is visible. Nothing is logged when the package is absent.

## 2.2.0 — 2026-09-16

- `django_utils.toolbox.outage`: dev/test-only outage switch — while on, every toolbox request fails as a refused
  connection (`ToolboxConnectionError`) without touching the network, and `status()` reads `unreachable`.
  Exists only with `DEBUG` or the new setting `AI_TOOLBOX_TEST_SWITCH = True`, never with
  `ENVIRONMENT == "production"`; the flag lives in the Django cache and expires after 15 min.

## 2.1.0 — 2026-09-15

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
