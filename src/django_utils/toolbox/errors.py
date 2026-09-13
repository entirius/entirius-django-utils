# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Exception hierarchy for the AI toolbox HTTP client."""

import httpx

__all__ = [
    "ToolboxError",
    "ToolboxNotConfiguredError",
    "ToolboxAuthError",
    "ToolboxModelNotAllowedError",
    "ToolboxNotFoundError",
    "ToolboxValidationError",
    "ToolboxBudgetExceededError",
    "ToolboxRateLimitError",
    "ToolboxTimeoutError",
    "ToolboxServerError",
    "ToolboxConnectionError",
    "error_from_response",
]

NOT_CONFIGURED_MESSAGE = "AI toolbox is not configured for this instance"


class ToolboxError(Exception):
    """Base exception for all toolbox client errors."""

    def __init__(
        self, status_code: int, message: str, code: str = "", field_errors: dict[str, list[str]] | None = None
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.code = code
        self.field_errors = field_errors or {}
        super().__init__(f"Toolbox HTTP {status_code}: {message}")


class ToolboxNotConfiguredError(ToolboxError):
    """Base URL, API key or channel is empty — the instance runs without the toolbox."""

    def __init__(self) -> None:
        super().__init__(0, NOT_CONFIGURED_MESSAGE, code="AI_TOOLBOX_NOT_CONFIGURED")


class ToolboxAuthError(ToolboxError):
    """API key rejected (401, or 403 without MODEL_NOT_ALLOWED)."""


class ToolboxModelNotAllowedError(ToolboxError):
    """Model missing from the channel's catalogue (403 MODEL_NOT_ALLOWED)."""


class ToolboxNotFoundError(ToolboxError):
    """Resource not found (404)."""


class ToolboxValidationError(ToolboxError):
    """Request rejected: 400 VALIDATION_ERROR or 422 SCHEMA_INVALID — ``code`` distinguishes."""


class ToolboxBudgetExceededError(ToolboxError):
    """Monthly budget exceeded (402)."""


class ToolboxRateLimitError(ToolboxError):
    """Rate limited: 503 UPSTREAM_RATE_LIMITED, or 429 from the translator (optional ``retry_after``)."""

    def __init__(self, *args, retry_after: float | None = None, **kwargs) -> None:
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


class ToolboxTimeoutError(ToolboxError):
    """504 UPSTREAM_TIMEOUT, or the client's own timeout (status 0)."""


class ToolboxServerError(ToolboxError):
    """Toolbox returned another 5xx."""


class ToolboxConnectionError(ToolboxError):
    """Network-level failure (DNS, connection refused, protocol error)."""


_BY_STATUS: dict[int, type[ToolboxError]] = {
    400: ToolboxValidationError,
    401: ToolboxAuthError,
    402: ToolboxBudgetExceededError,
    403: ToolboxAuthError,
    404: ToolboxNotFoundError,
    422: ToolboxValidationError,
    429: ToolboxRateLimitError,
    504: ToolboxTimeoutError,
}
_BY_CODE: dict[str, type[ToolboxError]] = {
    "MODEL_NOT_ALLOWED": ToolboxModelNotAllowedError,
    "UPSTREAM_RATE_LIMITED": ToolboxRateLimitError,
    "UPSTREAM_TIMEOUT": ToolboxTimeoutError,
}


def error_from_response(response: httpx.Response) -> ToolboxError:
    """Map a non-2xx toolbox response ``{"error", "message", "field_errors"?}`` to a typed error."""
    body = _json_object(response)
    status, code = response.status_code, str(body.get("error") or "")
    error_class = _BY_CODE.get(code) or _BY_STATUS.get(status)
    if error_class is None:
        error_class = ToolboxServerError if status >= 500 else ToolboxError
    message = str(body.get("message") or response.reason_phrase)
    field_errors = body.get("field_errors")
    kwargs = {"code": code, "field_errors": field_errors if isinstance(field_errors, dict) else None}
    if error_class is ToolboxRateLimitError:
        kwargs["retry_after"] = _retry_after(response)
    return error_class(status, message, **kwargs)


def _json_object(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None
