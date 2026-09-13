# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""DRF helper mapping toolbox errors to API responses — never the prompt, never the key."""

import logging
import uuid

from rest_framework import status
from rest_framework.response import Response

from django_utils.toolbox.errors import (
    ToolboxBudgetExceededError,
    ToolboxError,
    ToolboxModelNotAllowedError,
    ToolboxNotConfiguredError,
    ToolboxNotFoundError,
    ToolboxRateLimitError,
    ToolboxTimeoutError,
    ToolboxValidationError,
    parse_retry_after,
)

logger = logging.getLogger(__name__)

NOT_CONFIGURED_UI_MESSAGE = "AI features are available with the Entirius AI Toolbox."


def handle_toolbox_error(exc: ToolboxError) -> Response:
    """Map a ToolboxError to a DRF Response; unknown failures become a generic 502 with a debug id."""
    if isinstance(exc, ToolboxNotConfiguredError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "AI_TOOLBOX_NOT_CONFIGURED", NOT_CONFIGURED_UI_MESSAGE)
    if isinstance(exc, ToolboxBudgetExceededError):
        return _error(status.HTTP_402_PAYMENT_REQUIRED, "BUDGET_EXCEEDED", exc.message)
    if isinstance(exc, ToolboxModelNotAllowedError):
        return _error(status.HTTP_403_FORBIDDEN, "MODEL_NOT_ALLOWED", exc.message)
    if isinstance(exc, ToolboxNotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", exc.message)
    if isinstance(exc, ToolboxValidationError):
        return _validation_error(exc)
    if isinstance(exc, ToolboxRateLimitError):
        return _rate_limit_error(exc)
    if isinstance(exc, ToolboxTimeoutError):
        return _error(status.HTTP_504_GATEWAY_TIMEOUT, "UPSTREAM_TIMEOUT", "AI service timed out.")
    return _provider_error(exc)


def _error(http_status: int, code: str, message: str, **extra) -> Response:
    return Response({"error": code, "message": message, **extra}, status=http_status)


def _validation_error(exc: ToolboxValidationError) -> Response:
    http_status = exc.status_code if exc.status_code in (400, 422) else status.HTTP_400_BAD_REQUEST
    return _error(http_status, exc.code or "VALIDATION_ERROR", exc.message, field_errors=exc.field_errors)


def _rate_limit_error(exc: ToolboxRateLimitError) -> Response:
    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        http_status, code = status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMIT_EXCEEDED"
    else:
        http_status, code = status.HTTP_503_SERVICE_UNAVAILABLE, "UPSTREAM_RATE_LIMITED"
    response = _error(http_status, code, "AI service is rate limited.")
    retry_after = parse_retry_after(exc.retry_after)
    if retry_after is not None:
        response["Retry-After"] = str(int(retry_after))
    return response


def _provider_error(exc: ToolboxError) -> Response:
    debug_id = uuid.uuid4().hex[:8]
    logger.error(
        "Toolbox error [%s] (type=%s, status=%d, code=%s)", debug_id, type(exc).__name__, exc.status_code, exc.code
    )
    return _error(status.HTTP_502_BAD_GATEWAY, "PROVIDER_ERROR", "AI service error.", debug_id=debug_id)
