# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""make_exception_handler routing, including the no-v1-handler default."""

import pytest
from django.http import Http404
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.test import APIRequestFactory

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
