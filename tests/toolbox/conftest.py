# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest
from django.core.cache import cache

from django_utils.toolbox import CompletionRequest, Message
from django_utils.toolbox.testing import mock_toolbox

BASE_URL = "https://toolbox.test.internal"
CHANNEL = "zeno-test"
API_KEY = "dummy"


@pytest.fixture(autouse=True)
def toolbox_settings(settings):
    settings.AI_TOOLBOX_BASE_URL = BASE_URL
    settings.AI_TOOLBOX_API_KEY = API_KEY
    settings.AI_TOOLBOX_CHANNEL = CHANNEL
    cache.clear()
    yield settings
    cache.clear()


@pytest.fixture()
def router():
    with mock_toolbox() as mocked:
        yield mocked


@pytest.fixture()
def no_sleep(monkeypatch):
    monkeypatch.setattr("django_utils.toolbox.client.time.sleep", lambda _delay: None)


def make_request(**overrides) -> CompletionRequest:
    fields = {"model": "fake-chat", "messages": [Message(role="user", content="Hello")]} | overrides
    return CompletionRequest(**fields)
