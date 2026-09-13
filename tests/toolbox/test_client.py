# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""ToolboxClient: configuration, completion contract, error mapping, single-attempt policy."""

import json
from decimal import Decimal

import httpx
import pydantic
import pytest

from django_utils.toolbox import (
    CompletionRequest,
    CompletionResponse,
    Message,
    ModelInfo,
    ToolboxAuthError,
    ToolboxBudgetExceededError,
    ToolboxClient,
    ToolboxConnectionError,
    ToolboxError,
    ToolboxModelNotAllowedError,
    ToolboxNotConfiguredError,
    ToolboxRateLimitError,
    ToolboxServerError,
    ToolboxTimeoutError,
    ToolboxValidationError,
)
from django_utils.toolbox.testing import CANNED_MODELS, error_response

from .conftest import API_KEY, CHANNEL, make_request


@pytest.mark.parametrize("name", ["AI_TOOLBOX_BASE_URL", "AI_TOOLBOX_API_KEY", "AI_TOOLBOX_CHANNEL"])
def test_empty_setting_raises_not_configured(settings, name):
    setattr(settings, name, "")

    with pytest.raises(ToolboxNotConfiguredError) as exc_info:
        ToolboxClient()

    assert exc_info.value.message == "AI toolbox is not configured for this instance"


def test_invalid_channel_idx_rejected():
    with pytest.raises(ValueError, match="Invalid channel_idx"):
        ToolboxClient("../admin")


def test_complete_posts_contract_and_parses_response(router):
    with ToolboxClient() as client:
        response = client.complete(make_request(tags=["leads.draft"], temperature=0.3))

    assert isinstance(response, CompletionResponse)
    assert response.parsed == {"ok": True}
    assert response.cost == Decimal("0.000022")
    request = router["complete"].calls.last.request
    assert request.headers["X-API-Key"] == API_KEY
    assert json.loads(request.content) == {
        "model": "fake-chat",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.3,
        "tags": ["leads.draft"],
    }


def test_explicit_channel_overrides_setting(router):
    route = router.get("https://toolbox.test.internal/api/ai-completion/v2/admin/other/models/").mock(
        return_value=httpx.Response(200, json=[])
    )

    with ToolboxClient("other") as client:
        assert client.list_models() == []

    assert route.call_count == 1


def test_list_models_plain_list(router):
    with ToolboxClient() as client:
        models = client.list_models()

    assert models == [ModelInfo.model_validate(item) for item in CANNED_MODELS]
    assert models[0].input_price_per_1k == Decimal("0.001000")


def test_C10_budget_402_typed_error(router):
    router["complete"].mock(return_value=error_response(402, "BUDGET_EXCEEDED", "Monthly budget exceeded"))

    with ToolboxClient() as client, pytest.raises(ToolboxBudgetExceededError) as exc_info:
        client.complete(make_request())

    assert (exc_info.value.status_code, exc_info.value.code) == (402, "BUDGET_EXCEEDED")
    assert router["complete"].call_count == 1


def test_C11_schema_invalid_422(router):
    router["complete"].mock(return_value=error_response(422, "SCHEMA_INVALID", "'name' is a required property"))

    with ToolboxClient() as client, pytest.raises(ToolboxValidationError) as exc_info:
        client.complete(make_request(json_schema={"type": "object", "required": ["name"]}))

    assert (exc_info.value.status_code, exc_info.value.code) == (422, "SCHEMA_INVALID")
    assert router["complete"].call_count == 1


@pytest.mark.parametrize(
    ("side_effect", "error_class"),
    [
        (httpx.ConnectError("refused"), ToolboxConnectionError),
        (httpx.ReadTimeout("slow"), ToolboxTimeoutError),
        (error_response(504, "UPSTREAM_TIMEOUT"), ToolboxTimeoutError),
        (error_response(503, "UPSTREAM_RATE_LIMITED"), ToolboxRateLimitError),
        (error_response(500, "INTERNAL_ERROR"), ToolboxServerError),
    ],
)
def test_C12_single_attempt_transport_error_upstream(router, no_sleep, side_effect, error_class):
    router["complete"].mock(side_effect=[side_effect, httpx.Response(200, json={})])

    with ToolboxClient() as client, pytest.raises(error_class):
        client.complete(make_request())

    assert router["complete"].call_count == 1


def test_C33_model_not_allowed_403_typed_error(router):
    router["complete"].mock(return_value=error_response(403, "MODEL_NOT_ALLOWED", "Model not allowed"))

    with ToolboxClient() as client, pytest.raises(ToolboxModelNotAllowedError) as exc_info:
        client.complete(make_request(model="gpt-unlisted"))

    assert exc_info.value.code == "MODEL_NOT_ALLOWED"
    assert not isinstance(exc_info.value, ToolboxAuthError)


def test_403_without_model_code_is_auth_error(router):
    router["complete"].mock(return_value=error_response(403, "PERMISSION_DENIED"))

    with ToolboxClient() as client, pytest.raises(ToolboxAuthError):
        client.complete(make_request())


@pytest.mark.parametrize("failure", [error_response(502, "PROVIDER_ERROR"), httpx.ReadTimeout("slow")])
def test_complete_never_retries(router, no_sleep, failure):
    router["complete"].mock(side_effect=failure)

    with ToolboxClient(max_retries=5) as client, pytest.raises((ToolboxServerError, ToolboxTimeoutError)):
        client.complete(make_request())

    assert router["complete"].call_count == 1


def test_list_models_retries_on_5xx(router, no_sleep):
    router["models"].mock(side_effect=[error_response(503, "UPSTREAM_RATE_LIMITED"), httpx.Response(200, json=[])])

    with ToolboxClient() as client:
        assert client.list_models() == []

    assert router["models"].call_count == 2


def test_validation_error_reads_field_errors(router):
    field_errors = {"temperature": ["Input should be less than or equal to 2"]}
    router["complete"].mock(return_value=error_response(400, "VALIDATION_ERROR", "Invalid", field_errors))

    with ToolboxClient() as client, pytest.raises(ToolboxValidationError) as exc_info:
        client.complete(make_request())

    assert exc_info.value.field_errors == field_errors


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"tags": ["Upper"]}, "tags.0"),
        ({"tags": [f"t{i}" for i in range(11)]}, "tags"),
        ({"tags": ["x" * 65]}, "tags.0"),
        ({"temperature": 2.5}, "temperature"),
        ({"max_tokens": 0}, "max_tokens"),
        ({"max_tokens": 8193}, "max_tokens"),
        ({"messages": []}, "messages"),
    ],
)
def test_request_local_validation(router, overrides, field):
    with pytest.raises(pydantic.ValidationError):
        make_request(**overrides)

    fields = {"model": "fake-chat", "messages": [Message(role="user", content="Hi")], "json_schema": None} | overrides
    bypassed = CompletionRequest.model_construct(**fields)
    with ToolboxClient() as client, pytest.raises(ToolboxValidationError) as exc_info:
        client.complete(bypassed)

    assert field in exc_info.value.field_errors
    assert exc_info.value.status_code == 400
    assert router["complete"].call_count == 0


def test_request_forbids_unknown_fields():
    with pytest.raises(pydantic.ValidationError):
        CompletionRequest(model="fake-chat", messages=[{"role": "user", "content": "Hi"}], stream=True)


def test_channel_from_settings_is_used_in_url(router):
    with ToolboxClient() as client:
        client.list_models()

    assert f"/admin/{CHANNEL}/models/" in str(router["models"].calls.last.request.url)


@pytest.mark.parametrize(
    ("route", "body"),
    [
        ("complete", httpx.Response(200, json={"output": "x"})),
        ("complete", httpx.Response(200, text="<html>proxy</html>")),
        ("models", httpx.Response(200, json={"results": []})),
    ],
)
def test_malformed_success_body_is_typed_server_error(router, route, body):
    router[route].mock(return_value=body)

    with ToolboxClient() as client, pytest.raises(ToolboxServerError):
        client.complete(make_request()) if route == "complete" else client.list_models()


def test_non_dict_field_errors_ignored(router):
    router["complete"].mock(return_value=error_response(400, "VALIDATION_ERROR", "Invalid", [{"field": "items"}]))

    with ToolboxClient() as client, pytest.raises(ToolboxValidationError) as exc_info:
        client.complete(make_request())

    assert exc_info.value.field_errors == {}


def test_schema_invalid_message_not_echoed(router):
    model_output = '\'name\' is a required property in {"secret": "model output"}'
    router["complete"].mock(return_value=error_response(422, "SCHEMA_INVALID", model_output))

    with ToolboxClient() as client, pytest.raises(ToolboxValidationError) as exc_info:
        client.complete(make_request())

    assert model_output not in str(exc_info.value)
    assert model_output not in exc_info.value.message
    assert "SCHEMA_INVALID" in str(exc_info.value)
    assert exc_info.value.upstream_message == model_output


@pytest.mark.parametrize("value", ["-5", "nan", "inf", "301", "soon"])
def test_retry_after_negative_nan_inf_ignored(router, monkeypatch, value):
    delays: list[float] = []
    monkeypatch.setattr("django_utils.toolbox.client.time.sleep", delays.append)
    limited = httpx.Response(429, json={"error": "RATE_LIMIT_EXCEEDED"}, headers={"Retry-After": value})
    router["models"].mock(side_effect=[limited, httpx.Response(200, json=[])])

    with ToolboxClient() as client:
        assert client.list_models() == []

    assert delays == [2.0]


def test_get_retried_on_502(router, no_sleep):
    router["models"].mock(side_effect=[error_response(502, "PROVIDER_ERROR"), httpx.Response(200, json=[])])

    with ToolboxClient() as client:
        assert client.list_models() == []

    assert router["models"].call_count == 2


JOBS_URL = "https://toolbox.test.internal/api/ai-translator/v2/admin/zeno-test/jobs/"


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("dropped")])
def test_non_idempotent_post_not_retried_after_send(router, no_sleep, failure):
    route = router.post(JOBS_URL).mock(side_effect=[failure, httpx.Response(202, json={})])

    with ToolboxClient() as client, pytest.raises((ToolboxTimeoutError, ToolboxConnectionError)):
        client._post(JOBS_URL, {}, retry=False)

    assert route.call_count == 1


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_non_idempotent_post_not_retried_on_5xx(router, no_sleep, status_code):
    route = router.post(JOBS_URL).mock(side_effect=[error_response(status_code, "X"), httpx.Response(202, json={})])

    with ToolboxClient() as client, pytest.raises(ToolboxError):
        client._post(JOBS_URL, {}, retry=False)

    assert route.call_count == 1


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("refused"),
        httpx.Response(429, json={"error": "RATE_LIMIT_EXCEEDED"}, headers={"Retry-After": "1"}),
    ],
)
def test_non_idempotent_post_retried_before_send_or_on_429(router, no_sleep, failure):
    route = router.post(JOBS_URL).mock(side_effect=[failure, httpx.Response(202, json={"job_id": "j"})])

    with ToolboxClient() as client:
        assert client._post(JOBS_URL, {}, retry=False) == {"job_id": "j"}

    assert route.call_count == 2


def test_non_idempotent_post_429_without_retry_after_not_retried(router, no_sleep):
    limited = httpx.Response(429, json={"error": "RATE_LIMIT_EXCEEDED"}, headers={"Retry-After": "nan"})
    route = router.post(JOBS_URL).mock(side_effect=[limited, httpx.Response(202, json={})])

    with ToolboxClient() as client, pytest.raises(ToolboxRateLimitError):
        client._post(JOBS_URL, {}, retry=False)

    assert route.call_count == 1
