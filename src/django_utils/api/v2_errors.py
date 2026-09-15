# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""API v2 error handling.

All v2 error formatting lives here. The service's main/v2_errors.py becomes
a two-line config that builds the handler.

Usage in modules:
    from django_utils.api.v2_errors import raise_pydantic_as_drf

Usage in service settings:
    "EXCEPTION_HANDLER": "main.v2_errors.service_exception_handler"

Service main/v2_errors.py:
    from django_utils.api.v2_errors import make_exception_handler
    service_exception_handler = make_exception_handler()

Pass v1_handler= only when the service really installs its own handler for v1 paths;
with none, DRF's own handler serves them. See make_exception_handler.
"""

import logging
import uuid

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


# --- Pydantic Schemas ---


class ErrorDetail(BaseModel):
    """Single field-level error detail."""

    field: str | None = Field(None, description="Field name", examples=["sku"])
    location: str = Field("body", description="Parameter location: body, path, or query", examples=["body"])
    issue: str = Field(description="Machine-readable issue code", examples=["REQUIRED"])
    description: str = Field(description="Human-readable explanation", examples=["This field is required."])


class ErrorResponse(BaseModel):
    """Structured error response for all v2 API endpoints."""

    error: str = Field(description="Error code", examples=["VALIDATION_ERROR"])
    message: str = Field(description="Human-readable summary", examples=["Request validation failed."])
    debug_id: str = Field(description="Unique ID for support/debugging", examples=["f7a2c3b8"])
    details: list[ErrorDetail] = Field(default_factory=list, description="Field-level error details")


# --- Error Code Mapping ---

_DRF_TO_ERROR_CODE = {
    "ValidationError": "VALIDATION_ERROR",
    "ParseError": "INVALID_REQUEST",
    "NotAuthenticated": "AUTHENTICATION_REQUIRED",
    "AuthenticationFailed": "AUTHENTICATION_REQUIRED",
    "PermissionDenied": "PERMISSION_DENIED",
    "NotFound": "NOT_FOUND",
    "MethodNotAllowed": "INVALID_REQUEST",
    "NotAcceptable": "INVALID_REQUEST",
    "Throttled": "RATE_LIMITED",
    "UnsupportedMediaType": "INVALID_REQUEST",
}

_STATUS_TO_MESSAGE = {
    400: "Request validation failed.",
    401: "Authentication credentials were not provided or are invalid.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "HTTP method not allowed.",
    429: "Request was throttled.",
    500: "An internal error occurred.",
}


# --- Helpers ---


def _generate_debug_id() -> str:
    return uuid.uuid4().hex[:8]


def _build_validation_details(detail: dict | list | str) -> list[ErrorDetail]:
    """Convert DRF validation error detail into structured ErrorDetail list."""
    details = []

    if isinstance(detail, dict):
        for field_name, errors in detail.items():
            if isinstance(errors, list):
                for error in errors:
                    issue = str(error.code).upper() if hasattr(error, "code") else "INVALID"
                    details.append(
                        ErrorDetail(
                            field=field_name if field_name != "non_field_errors" else None,
                            location="body",
                            issue=issue,
                            description=str(error),
                        )
                    )
            else:
                details.append(
                    ErrorDetail(
                        field=field_name if field_name != "non_field_errors" else None,
                        location="body",
                        issue="INVALID",
                        description=str(errors),
                    )
                )
    elif isinstance(detail, list):
        for error in detail:
            details.append(ErrorDetail(field=None, location="body", issue="INVALID", description=str(error)))

    return details


def _conflict_parts(exc: drf_exceptions.APIException) -> tuple[str, str, list[ErrorDetail]]:
    """A 409 keeps what the exception carries: its code as `error`, its detail as message or field details."""
    detail = exc.detail
    if isinstance(detail, dict | list):
        return "CONFLICT", "The request conflicts with the current state.", _build_validation_details(detail)
    code = str(getattr(detail, "code", "") or "conflict").upper()
    return code, str(detail) or "An error occurred.", []


# --- Exception Handlers ---


def v2_exception_handler(exc, context):
    """Handle exceptions for v2 endpoints with structured error responses."""
    debug_id = _generate_debug_id()

    handled = drf_exception_handler(exc, context)

    if handled is not None:
        exc_class = type(exc).__name__
        error_code = _DRF_TO_ERROR_CODE.get(exc_class, "INVALID_REQUEST")
        status_code = handled.status_code
        message = _STATUS_TO_MESSAGE.get(status_code, "An error occurred.")

        details = []
        if isinstance(exc, drf_exceptions.ValidationError):
            details = _build_validation_details(handled.data)
        elif status_code == 409 and isinstance(exc, drf_exceptions.APIException):
            error_code, message, details = _conflict_parts(exc)

        error_response = ErrorResponse(error=error_code, message=message, debug_id=debug_id, details=details)

        logger.warning("v2 API error [%s] %s: %s (debug_id=%s)", status_code, error_code, exc, debug_id)

        return Response(error_response.model_dump(), status=status_code, exception=True)

    # Unhandled exception — 500, no details leaked
    logger.exception("Unhandled v2 API error (debug_id=%s): %s", debug_id, exc)

    error_response = ErrorResponse(
        error="INTERNAL_ERROR", message="An internal error occurred.", debug_id=debug_id, details=[]
    )

    return Response(error_response.model_dump(), status=500, exception=True)


# --- Public API ---


def raise_pydantic_as_drf(exc: PydanticValidationError) -> None:
    """Convert Pydantic ValidationError into DRF ValidationError."""
    detail: dict[str, list[str]] = {}
    for error in exc.errors():
        field_name = ".".join(str(loc) for loc in error["loc"]) or "non_field_errors"
        detail.setdefault(field_name, []).append(error["msg"])
    raise drf_exceptions.ValidationError(detail)


def make_exception_handler(v1_handler=None):
    """Factory: returns a DRF exception handler that routes v1/v2 based on URL path.

    Usage in service main/v2_errors.py:
        from django_utils.api.v2_errors import make_exception_handler
        service_exception_handler = make_exception_handler()

    Pass v1_handler only when the service installs a handler for its v1 paths. If the
    module providing that handler is optional, import it defensively: DRF resolves
    EXCEPTION_HANDLER lazily, at the first error, so an ImportError here does not fail
    at startup -- it turns every error response in the API into a bare 500.
    """

    def handler(exc, context):
        request = context.get("request")
        if request and hasattr(request, "path") and request.path.startswith("/api/") and "/v2/" in request.path:
            return v2_exception_handler(exc, context)
        if v1_handler:
            return v1_handler(exc, context)
        return drf_exception_handler(exc, context)

    return handler
