# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""status(): unconfigured without network, configured cached, unreachable on any failure."""

import httpx
import pytest
import respx
from django.core.cache import cache

from django_utils.toolbox import ToolboxStatus, status
from django_utils.toolbox.status import CACHE_KEY
from django_utils.toolbox.testing import error_response


@pytest.mark.parametrize("name", ["AI_TOOLBOX_BASE_URL", "AI_TOOLBOX_API_KEY", "AI_TOOLBOX_CHANNEL"])
def test_status_unconfigured_no_network(settings, name):
    setattr(settings, name, "")

    with respx.mock(assert_all_mocked=True) as mocked:
        assert status() == ToolboxStatus.UNCONFIGURED

    assert mocked.calls.call_count == 0


def test_status_configured_cached(router):
    assert status() == ToolboxStatus.CONFIGURED
    assert status() == ToolboxStatus.CONFIGURED

    assert router["models"].call_count == 1
    assert cache.get(CACHE_KEY) == "configured"


def test_status_probe_uses_short_timeout(router):
    status()

    timeout = router["models"].calls.last.request.extensions["timeout"]
    assert timeout["read"] == 5.0


@pytest.mark.parametrize(
    "failure", [httpx.ConnectError("refused"), error_response(401, "AUTHENTICATION_REQUIRED"), error_response(500, "X")]
)
def test_status_unreachable(router, failure):
    router["models"].mock(side_effect=failure)

    assert status() == ToolboxStatus.UNREACHABLE
    assert router["models"].call_count == 1


def test_status_never_raises_when_cache_fails(router, monkeypatch):
    def broken(*_args, **_kwargs):
        raise ConnectionError("cache down")

    monkeypatch.setattr(cache, "get", broken)

    assert status() == ToolboxStatus.UNREACHABLE
