# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""make_exception_handler routing, including the no-v1-handler default."""

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory

from django_utils.api.v2_errors import make_exception_handler


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
