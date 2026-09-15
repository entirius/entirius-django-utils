# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Exception hierarchy for the AI toolbox HTTP client."""

import math

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
    "parse_retry_after",
]

NOT_CONFIGURED_MESSAGE = "AI toolbox is not configured for this instance"
MAX_RETRY_AFTER = 300.0


class ToolboxError(Exception):
    """Base exception for all toolbox client errors.

    ``upstream_message`` keeps the toolbox's own text (it may quote model output): never log it, never render it.
    """

    default_message = "AI toolbox request failed."

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str = "",
        field_errors: dict[str, list[str]] | None = None,
        upstream_message: str = "",
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.code = code
        self.field_errors = field_errors or {}
        self.upstream_message = upstream_message
        prefix = f"Toolbox HTTP {status_code} {code}" if code else f"Toolbox HTTP {status_code}"
        super().__init__(f"{prefix}: {message}")


class ToolboxNotConfiguredError(ToolboxError):
    """Base URL, API key or channel is empty — the instance runs without the toolbox."""

    def __init__(self) -> None:
        super().__init__(0, NOT_CONFIGURED_MESSAGE, code="AI_TOOLBOX_NOT_CONFIGURED")


class ToolboxAuthError(ToolboxError):
    """API key rejected (401, or 403 without MODEL_NOT_ALLOWED)."""

    default_message = "AI toolbox rejected the API key."


class ToolboxModelNotAllowedError(ToolboxError):
    """Model missing from the channel's catalogue (403 MODEL_NOT_ALLOWED)."""

    default_message = "Model is not allowed for this channel."


class ToolboxNotFoundError(ToolboxError):
    """Resource not found (404)."""

    default_message = "Resource not found."


class ToolboxValidationError(ToolboxError):
    """Request rejected: 400 VALIDATION_ERROR or 422 SCHEMA_INVALID — ``code`` distinguishes."""

    default_message = "AI toolbox rejected the request."


class ToolboxBudgetExceededError(ToolboxError):
    """Monthly budget exceeded (402)."""

    default_message = "Monthly budget exceeded."


class ToolboxRateLimitError(ToolboxError):
    """Rate limited: 503 UPSTREAM_RATE_LIMITED, or 429 from the translator (optional ``retry_after``)."""

    default_message = "AI service is rate limited."

    def __init__(self, *args, retry_after: float | None = None, **kwargs) -> None:
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


class ToolboxTimeoutError(ToolboxError):
    """504 UPSTREAM_TIMEOUT, or the client's own timeout (status 0)."""

    default_message = "AI service timed out."


class ToolboxServerError(ToolboxError):
    """Toolbox returned another 5xx."""

    default_message = "AI toolbox server error."


class ToolboxConnectionError(ToolboxError):
    """Network-level failure (DNS, connection refused, protocol error)."""

    default_message = "AI toolbox connection failed."


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
    field_errors = body.get("field_errors")
    kwargs = {
        "code": code,
        "field_errors": field_errors if isinstance(field_errors, dict) else None,
        "upstream_message": str(body.get("message") or ""),
    }
    if error_class is ToolboxRateLimitError:
        kwargs["retry_after"] = parse_retry_after(response.headers.get("Retry-After"))
    return error_class(status, error_class.default_message, **kwargs)


def _json_object(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def parse_retry_after(value: object) -> float | None:
    """Seconds from a ``Retry-After`` value; anything but a finite number in [0, 300] counts as absent."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if math.isfinite(seconds) and 0 <= seconds <= MAX_RETRY_AFTER else None
