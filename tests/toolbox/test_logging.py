# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The API key and the prompt never reach a log record, success or failure, at any level."""

import logging

import httpx
import pytest

from django_utils.toolbox import Message, ToolboxClient, ToolboxServerError, handle_toolbox_error, status
from django_utils.toolbox.testing import error_response

from .conftest import API_KEY, make_request

PROMPT = "PROMPT-distinctive-lead-text"


def test_logging_never_contains_key_or_prompt(router, no_sleep, caplog):
    caplog.set_level(logging.DEBUG)
    ok = httpx.Response(200, json=[])
    router["models"].mock(side_effect=[error_response(503, "UPSTREAM_RATE_LIMITED"), ok, ok])
    router["complete"].mock(return_value=error_response(500, "INTERNAL_ERROR"))

    with ToolboxClient() as client:
        client.list_models()
        with pytest.raises(ToolboxServerError) as exc_info:
            client.complete(make_request(messages=[Message(role="user", content=PROMPT)]))
    handle_toolbox_error(exc_info.value)
    status()

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "Toolbox request POST" in logged
    assert "retrying" in logged
    assert API_KEY not in logged
    assert PROMPT not in logged
