# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Outage switch (FIX-16 item 3): gated to DEBUG / AI_TOOLBOX_TEST_SWITCH, never production, no network while on."""

import pytest
from django.core.cache import cache

from django_utils.toolbox import ToolboxClient, ToolboxConnectionError, ToolboxStatus, outage, status
from django_utils.toolbox.status import CACHE_KEY as STATUS_CACHE_KEY

from .conftest import make_request


@pytest.fixture()
def switchable(settings):
    settings.DEBUG = False
    settings.AI_TOOLBOX_TEST_SWITCH = True
    return settings


@pytest.mark.parametrize(
    ("debug", "switch", "expected"), [(False, False, False), (True, False, True), (False, True, True)]
)
def test_item3_switch_exists_only_with_debug_or_setting(settings, debug, switch, expected):
    settings.DEBUG, settings.AI_TOOLBOX_TEST_SWITCH = debug, switch

    assert outage.allowed() is expected


def test_item3_switch_never_exists_in_production(switchable):
    switchable.DEBUG = True
    switchable.ENVIRONMENT = "production"

    with pytest.raises(outage.OutageSwitchDisabledError):
        outage.set_down(True)
    assert outage.allowed() is False


def test_item3_disabled_switch_ignores_a_stored_flag(settings, router):
    settings.DEBUG, settings.AI_TOOLBOX_TEST_SWITCH = False, False
    cache.set(outage.CACHE_KEY, True)

    with ToolboxClient() as client:
        client.complete(make_request())

    assert router["complete"].call_count == 1


def test_item3_switch_on_fails_every_request_without_network(switchable, router):
    outage.set_down(True)

    with pytest.raises(ToolboxConnectionError), ToolboxClient() as client:
        client.complete(make_request())

    assert router["complete"].call_count == 0
    assert status() == ToolboxStatus.UNREACHABLE
    assert router["models"].call_count == 0


def test_item3_switch_off_restores_requests_and_drops_cached_status(switchable, router):
    outage.set_down(True)
    assert status() == ToolboxStatus.UNREACHABLE

    outage.set_down(False)

    assert cache.get(STATUS_CACHE_KEY) is None
    assert status() == ToolboxStatus.CONFIGURED
    assert outage.is_down() is False


def test_item3_switch_on_expires(switchable, monkeypatch):
    calls = []
    monkeypatch.setattr(cache, "set", lambda *args: calls.append(args))

    outage.set_down(True)

    assert calls == [(outage.CACHE_KEY, True, outage.OUTAGE_TTL_S)]
