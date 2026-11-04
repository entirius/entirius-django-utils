# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""make_exception_handler routing, including the no-v1-handler default."""

import pytest
from django.http import Http404
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import APIException, NotFound, Throttled, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_exception_handler

from django_utils.api.v2_errors import make_exception_handler, raise_pydantic_as_drf


def _context(path):
    return {"request": APIRequestFactory().get(path)}


@pytest.mark.parametrize("path", ["/api/thing/v1/x/", "/api/thing/v2/x/"])
def test_default_factory_handles_both_api_versions(path):
    """No v1_handler is the documented default; DRF's own handler serves v1."""
    response = make_exception_handler()(NotFound(), _context(path))

    assert response is not None
    assert response.status_code == 404


def test_v2_path_uses_the_v2_envelope():
    response = make_exception_handler()(NotFound(), _context("/api/thing/v2/x/"))

    assert set(response.data) >= {"error", "message", "debug_id"}


def test_v1_handler_is_used_when_one_is_supplied():
    sentinel = object()
    handler = make_exception_handler(v1_handler=lambda exc, ctx: sentinel)

    assert handler(NotFound(), _context("/api/thing/v1/x/")) is sentinel


class _Conflict(APIException):
    status_code = 409
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"


def _v2(exc):
    return make_exception_handler()(exc, _context("/api/thing/v2/x/"))


def test_item11_conflict_keeps_code_and_message():
    response = _v2(_Conflict("message already reviewed", code="already_reviewed"))

    assert response.status_code == 409
    assert response.data["error"] == "ALREADY_REVIEWED"
    assert response.data["message"] == "message already reviewed"


def test_item11_conflict_without_detail_uses_the_class_default():
    response = _v2(_Conflict())

    assert response.data["error"] == "CONFLICT"
    assert response.data["message"] == "The request conflicts with the current state."


def test_item11_conflict_keeps_field_details():
    response = _v2(_Conflict({"domain": ["already exists"]}))

    assert response.data["error"] == "CONFLICT"
    assert response.data["details"][0]["field"] == "domain"
    assert response.data["details"][0]["description"] == "already exists"


def test_item11_other_statuses_keep_the_generic_message():
    response = _v2(NotFound("secret row 42"))

    assert response.data["message"] == "The requested resource was not found."


def test_django_http404_reads_not_found():
    """get_object_or_404 raises Django's Http404, not DRF's NotFound."""
    response = _v2(Http404("No ProductRepresentation matches the given query."))

    assert response.status_code == 404
    assert response.data["error"] == "NOT_FOUND"
    assert response.data["message"] == "The requested resource was not found."


class _Filters(BaseModel):
    current: bool


def _pydantic_error(**kwargs):
    with pytest.raises(PydanticValidationError) as invalid:
        _Filters(current="maybe")
    with pytest.raises(ValidationError) as raised:
        raise_pydantic_as_drf(invalid.value, **kwargs)
    return raised.value


def test_issue12_pydantic_error_defaults_to_body():
    response = _v2(_pydantic_error())

    assert response.status_code == 400
    assert [d["location"] for d in response.data["details"]] == ["body"]


def test_issue12_query_schema_reports_location_query():
    response = _v2(_pydantic_error(location="query"))

    assert response.data["error"] == "VALIDATION_ERROR"
    assert response.data["details"][0]["field"] == "current"
    assert [d["location"] for d in response.data["details"]] == ["query"]


# --- Headers DRF sets on the error response (WWW-Authenticate, Retry-After) ---

V2_PATH = "/api/thing/v2/x/"


class _BasicAuthView(APIView):
    """First authenticator has authenticate_header: DRF answers 401 with WWW-Authenticate."""

    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return make_exception_handler()

    def get(self, request):
        return Response({})


class _SessionAuthView(_BasicAuthView):
    """First authenticator has no authenticate_header: DRF turns the 401 into a 403."""

    authentication_classes = [SessionAuthentication]


class _SlowDown(BaseThrottle):
    def allow_request(self, request, view):
        return False

    def wait(self):
        return 2.3


class _ThrottledView(_BasicAuthView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [_SlowDown]


def _get(view, **headers):
    return view.as_view()(APIRequestFactory().get(V2_PATH, **headers))


def test_missing_credentials_keep_www_authenticate():
    response = _get(_BasicAuthView)

    assert response.status_code == 401
    assert response.data["error"] == "AUTHENTICATION_REQUIRED"
    assert response["WWW-Authenticate"] == 'Basic realm="api"'


def test_failed_authentication_keeps_www_authenticate():
    response = _get(_BasicAuthView, HTTP_AUTHORIZATION="Basic not-base64!")

    assert response.status_code == 401
    assert response.data["error"] == "AUTHENTICATION_REQUIRED"
    assert response["WWW-Authenticate"] == 'Basic realm="api"'


def test_authenticator_without_header_stays_a_403():
    response = _get(_SessionAuthView)

    assert response.status_code == 403
    assert "WWW-Authenticate" not in response


def test_throttled_keeps_drf_retry_after():
    response = _get(_ThrottledView)

    assert response.status_code == 429
    assert response.data["error"] == "RATE_LIMITED"
    drf_response = drf_exception_handler(Throttled(wait=2.3), _context(V2_PATH))
    assert response["Retry-After"] == drf_response["Retry-After"] == "3"


def test_throttled_without_wait_has_no_retry_after():
    response = _v2(Throttled())

    assert response.status_code == 429
    assert "Retry-After" not in response


def test_validation_error_adds_no_headers():
    response = _v2(ValidationError({"sku": ["This field is required."]}))

    assert response.status_code == 400
    assert set(response.headers) == set(Response().headers)
