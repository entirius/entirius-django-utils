# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""handle_toolbox_error: every error class maps to a stable status + code, nothing upstream leaks."""

import pytest

from django_utils.toolbox import (
    ToolboxAuthError,
    ToolboxBudgetExceededError,
    ToolboxConnectionError,
    ToolboxError,
    ToolboxModelNotAllowedError,
    ToolboxNotConfiguredError,
    ToolboxNotFoundError,
    ToolboxRateLimitError,
    ToolboxServerError,
    ToolboxTimeoutError,
    ToolboxValidationError,
    handle_toolbox_error,
)

UPSTREAM_SECRET = "upstream detail with prompt text"


@pytest.mark.parametrize(
    ("exc", "http_status", "code"),
    [
        (ToolboxNotConfiguredError(), 503, "AI_TOOLBOX_NOT_CONFIGURED"),
        (ToolboxBudgetExceededError(402, "Monthly budget exceeded", "BUDGET_EXCEEDED"), 402, "BUDGET_EXCEEDED"),
        (ToolboxModelNotAllowedError(403, "Model not allowed", "MODEL_NOT_ALLOWED"), 403, "MODEL_NOT_ALLOWED"),
        (ToolboxNotFoundError(404, "Job not found", "NOT_FOUND"), 404, "NOT_FOUND"),
        (ToolboxValidationError(400, "Invalid", "VALIDATION_ERROR", {"model": ["required"]}), 400, "VALIDATION_ERROR"),
        (ToolboxValidationError(422, "'a' is required", "SCHEMA_INVALID"), 422, "SCHEMA_INVALID"),
        (ToolboxRateLimitError(503, UPSTREAM_SECRET, "UPSTREAM_RATE_LIMITED"), 503, "UPSTREAM_RATE_LIMITED"),
        (ToolboxRateLimitError(429, UPSTREAM_SECRET, retry_after=30.0), 429, "RATE_LIMIT_EXCEEDED"),
        (ToolboxTimeoutError(504, UPSTREAM_SECRET, "UPSTREAM_TIMEOUT"), 504, "UPSTREAM_TIMEOUT"),
        (ToolboxTimeoutError(0, "Request timed out: ReadTimeout", "UPSTREAM_TIMEOUT"), 504, "UPSTREAM_TIMEOUT"),
        (ToolboxAuthError(401, UPSTREAM_SECRET), 502, "PROVIDER_ERROR"),
        (ToolboxServerError(500, UPSTREAM_SECRET), 502, "PROVIDER_ERROR"),
        (ToolboxConnectionError(0, UPSTREAM_SECRET), 502, "PROVIDER_ERROR"),
        (ToolboxError(418, UPSTREAM_SECRET), 502, "PROVIDER_ERROR"),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else None,
)
def test_handle_toolbox_error_matrix(exc, http_status, code):
    response = handle_toolbox_error(exc)

    assert response.status_code == http_status
    assert response.data["error"] == code
    assert UPSTREAM_SECRET not in str(response.data)


def test_not_configured_message_points_to_toolbox():
    response = handle_toolbox_error(ToolboxNotConfiguredError())

    assert response.data["message"] == "AI features are available with the Entirius AI Toolbox."


def test_validation_carries_field_errors():
    response = handle_toolbox_error(ToolboxValidationError(400, "Invalid", "VALIDATION_ERROR", {"model": ["required"]}))

    assert response.data["field_errors"] == {"model": ["required"]}


def test_provider_error_has_debug_id():
    response = handle_toolbox_error(ToolboxServerError(500, "boom"))

    assert response.data["message"] == "AI service error."
    assert len(response.data["debug_id"]) == 8


def test_rate_limit_sets_retry_after_header():
    response = handle_toolbox_error(ToolboxRateLimitError(429, "slow down", retry_after=30.0))

    assert response["Retry-After"] == "30"
