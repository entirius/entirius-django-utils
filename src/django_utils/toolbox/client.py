# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Thin HTTP client for the remote AI toolbox service.

Transport only: sends requests, maps errors to typed exceptions, returns parsed bodies.
No prompts, no domain logic — those belong to the calling module.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from django_utils.toolbox import settings as toolbox_settings
from django_utils.toolbox.errors import (
    ToolboxConnectionError,
    ToolboxError,
    ToolboxNotConfiguredError,
    ToolboxRateLimitError,
    ToolboxServerError,
    ToolboxTimeoutError,
    ToolboxValidationError,
    error_from_response,
    parse_retry_after,
)
from django_utils.toolbox.schemas import CompletionRequest, CompletionResponse, ModelInfo

logger = logging.getLogger(__name__)

# httpx logs every request at INFO; keep it quiet so request lines never reach service logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

_RETRYABLE_STATUSES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_BASE_DELAY = 2.0
_RETRY_MAX_DELAY = 60.0
_CHANNEL_IDX_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_COMPLETION_TOOL = "ai-completion"


def _log_request(request: httpx.Request) -> None:
    """httpx event hook: method, URL and headers with the API key redacted — never the body."""
    headers = {k: ("<redacted>" if k.lower() == "x-api-key" else v) for k, v in request.headers.items()}
    logger.debug("Toolbox request %s %s headers=%s", request.method, request.url, headers)


class ToolboxClient:
    """Synchronous HTTP client for the AI toolbox REST API.

    Usage::

        with ToolboxClient() as client:
            response = client.complete(CompletionRequest(model="fake-chat", messages=[...]))
    """

    def __init__(self, channel_idx: str | None = None, *, max_retries: int | None = None) -> None:
        base_url, api_key = toolbox_settings.AI_TOOLBOX_BASE_URL, toolbox_settings.AI_TOOLBOX_API_KEY
        channel_idx = toolbox_settings.AI_TOOLBOX_CHANNEL if channel_idx is None else channel_idx
        if not (base_url and api_key and channel_idx):
            raise ToolboxNotConfiguredError()
        if not _CHANNEL_IDX_PATTERN.match(channel_idx):
            raise ValueError(f"Invalid channel_idx: {channel_idx!r}")

        self._channel_idx = channel_idx
        self._base_url = base_url.rstrip("/")
        self._max_retries = toolbox_settings.AI_TOOLBOX_MAX_RETRIES if max_retries is None else max_retries
        self._client = httpx.Client(
            headers={"X-API-Key": api_key},
            timeout=toolbox_settings.AI_TOOLBOX_TIMEOUT,
            event_hooks={"request": [_log_request]},
        )

    # --- Completion endpoints ---

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """POST complete/ — paid and non-idempotent: exactly one HTTP attempt, never retried."""
        payload = _validated_payload(request)
        url = self._url(_COMPLETION_TOOL, "complete/")
        body = self._request("POST", url, json=payload, timeout=toolbox_settings.AI_COMPLETION_TIMEOUT, retries=0)
        return _parse(CompletionResponse, body)

    def list_models(self, *, timeout: float | None = None) -> list[ModelInfo]:
        """GET models/ — catalogue models allowed for this channel (plain list)."""
        body = self._get(self._url(_COMPLETION_TOOL, "models/"), timeout=timeout)
        return _parse(list[ModelInfo], body)

    # --- URL helpers ---

    def _url(self, tool: str, path: str) -> str:
        return f"{self._base_url}/api/{tool}/v2/admin/{self._channel_idx}/{path}"

    # --- Transport ---

    def _get(self, url: str, params: dict | None = None, timeout: float | None = None) -> Any:
        return self._request("GET", url, params=params, timeout=timeout, retries=self._max_retries - 1)

    def _post(self, url: str, payload: dict, *, retry: bool = True) -> Any:
        """``retry=False`` for paid, non-idempotent calls: re-sent only when the request never left or on 429."""
        return self._request("POST", url, json=payload, retries=self._max_retries - 1, idempotent=retry)

    def _request(
        self, method: str, url: str, *, retries: int, timeout: float | None = None, idempotent: bool = True, **kwargs
    ) -> Any:
        """Send with up to ``retries`` extra attempts on 5xx/408/429/transport errors (backoff 2→60 s)."""
        timeout = toolbox_settings.AI_TOOLBOX_TIMEOUT if timeout is None else timeout
        attempt = 0
        while True:
            try:
                return self._send(method, url, timeout=timeout, **kwargs)
            except ToolboxError as exc:
                if attempt >= retries or not _is_retryable(exc, idempotent):
                    raise
                self._sleep_before_retry(attempt, exc)
                attempt += 1

    def _send(self, method: str, url: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ToolboxTimeoutError(0, f"Request timed out: {type(exc).__name__}", "UPSTREAM_TIMEOUT") from None
        except httpx.ConnectError as exc:
            error = ToolboxConnectionError(0, f"Connection failed: {type(exc).__name__}")
            error.request_sent = False
            raise error from None
        except httpx.HTTPError as exc:
            raise ToolboxConnectionError(0, f"Connection failed: {type(exc).__name__}") from None
        if not response.is_success:
            raise error_from_response(response)
        try:
            return response.json()
        except ValueError:
            raise ToolboxServerError(response.status_code, "Toolbox returned a non-JSON body") from None

    def _sleep_before_retry(self, attempt: int, error: ToolboxError) -> None:
        retry_after = parse_retry_after(error.retry_after) if isinstance(error, ToolboxRateLimitError) else None
        if retry_after is not None:
            delay = min(retry_after, _RETRY_MAX_DELAY)
        else:
            delay = min(_RETRY_BASE_DELAY * (2**attempt), _RETRY_MAX_DELAY)
        logger.warning(
            "Toolbox request failed (attempt %d/%d, %s), retrying in %.1fs",
            attempt + 1,
            self._max_retries,
            type(error).__name__,
            delay,
        )
        time.sleep(delay)

    # --- Lifecycle ---

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ToolboxClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _is_retryable(error: ToolboxError, idempotent: bool) -> bool:
    if not idempotent:
        return _never_sent(error) or _rate_limited_with_retry_after(error)
    if isinstance(error, (ToolboxConnectionError, ToolboxTimeoutError)):
        return True
    return error.status_code in _RETRYABLE_STATUSES


def _never_sent(error: ToolboxError) -> bool:
    return getattr(error, "request_sent", True) is False


def _rate_limited_with_retry_after(error: ToolboxError) -> bool:
    if not isinstance(error, ToolboxRateLimitError) or error.status_code != 429:
        return False
    return parse_retry_after(error.retry_after) is not None


def _parse(schema: Any, body: Any) -> Any:
    """Validate a 2xx body against the contract; a mismatch is a typed server error, never raw pydantic."""
    try:
        return TypeAdapter(schema).validate_python(body)
    except ValidationError:
        raise ToolboxServerError(200, "Toolbox response does not match the contract") from None


def _validated_payload(request: CompletionRequest) -> dict:
    """Re-validate locally (the request may have been built with ``model_construct``) before any network call."""
    try:
        checked = CompletionRequest.model_validate(request.model_dump())
    except ValidationError as exc:
        field_errors: dict[str, list[str]] = {}
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"]) or "non_field_errors"
            field_errors.setdefault(field, []).append(error["msg"])
        raise ToolboxValidationError(400, "Request validation failed.", "VALIDATION_ERROR", field_errors) from None
    return checked.model_dump(mode="json", exclude_none=True)
