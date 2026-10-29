# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import sys
import types

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle

from django_utils.api.client_ip import ClientIPThrottleMixin, get_client_ip
from django_utils.api.decorators import verify_captcha

CF = "HTTP_CF_CONNECTING_IP"


def _request(**meta):
    return RequestFactory().get("/", **meta)


def test_header_set_wins_over_xff(settings):
    settings.CLIENT_IP_HEADER = CF
    request = _request(**{CF: " 1.2.3.4 ", "HTTP_X_FORWARDED_FOR": "6.6.6.6"})
    assert get_client_ip(request) == "1.2.3.4"


def test_accepts_drf_request(settings):
    settings.CLIENT_IP_HEADER = CF
    assert get_client_ip(Request(_request(**{CF: "1.2.3.4"}))) == "1.2.3.4"


@pytest.mark.parametrize("meta", [{}, {CF: ""}, {CF: "   "}])
def test_header_absent_or_empty_falls_back(settings, meta):
    settings.CLIENT_IP_HEADER = CF
    assert get_client_ip(_request(REMOTE_ADDR="9.9.9.9", **meta)) == "9.9.9.9"


def test_unset_setting_keeps_drf_behaviour():
    request = _request(REMOTE_ADDR="9.9.9.9", **{CF: "1.2.3.4"})
    assert get_client_ip(request) == "9.9.9.9"


def test_num_proxies_fallback(settings):
    settings.REST_FRAMEWORK = {"NUM_PROXIES": 1}
    from rest_framework.settings import api_settings

    api_settings.reload()
    try:
        request = _request(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 5.5.5.5")
        assert get_client_ip(request) == "5.5.5.5"
    finally:
        settings.REST_FRAMEWORK = {}
        api_settings.reload()


def test_mixin_on_throttle(settings):
    class Throttle(ClientIPThrottleMixin, AnonRateThrottle):
        rate = "10/hour"

    settings.CLIENT_IP_HEADER = CF
    request = Request(_request(**{CF: "1.2.3.4", "HTTP_X_FORWARDED_FOR": "6.6.6.6"}))
    assert Throttle().get_cache_key(request, None) == "throttle_anon_1.2.3.4"


def _view(request):
    return None


@pytest.fixture
def no_captcha(monkeypatch):
    monkeypatch.setitem(sys.modules, "django_captcha", None)


def test_missing_captcha_warns_and_passes(no_captcha, caplog):
    with caplog.at_level(logging.WARNING):
        assert verify_captcha(_view) is _view
    assert "not installed" in caplog.text
    assert "_view" in caplog.text


def test_captcha_required_raises_on_import_error(no_captcha, settings):
    settings.CAPTCHA_REQUIRED = True
    with pytest.raises(ImproperlyConfigured):
        verify_captcha(_view)


def _broken_captcha(monkeypatch):
    class Broken(types.ModuleType):
        def __getattr__(self, name):
            raise RuntimeError("not in INSTALLED_APPS")

    for name in ("django_captcha", "django_captcha.output", "django_captcha.output.decorators"):
        monkeypatch.setitem(sys.modules, name, Broken(name))


def test_captcha_runtime_error_warns(monkeypatch, caplog):
    _broken_captcha(monkeypatch)
    with caplog.at_level(logging.WARNING):
        assert verify_captcha(_view) is _view
    assert "not in INSTALLED_APPS" in caplog.text


def test_captcha_required_raises_on_runtime_error(settings, monkeypatch):
    settings.CAPTCHA_REQUIRED = True
    _broken_captcha(monkeypatch)
    with pytest.raises(ImproperlyConfigured):
        verify_captcha(_view)
