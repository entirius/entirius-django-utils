# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test helpers for modules calling the toolbox (requires ``respx`` — the ``test`` extra).

Usage::

    from django_utils.toolbox.testing import error_response, mock_toolbox

    def test_budget(settings):
        with mock_toolbox() as router:
            router["complete"].mock(return_value=error_response(402, "BUDGET_EXCEEDED"))
            ...
"""

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import respx

from django_utils.toolbox import settings as toolbox_settings

CANNED_COMPLETION: dict = {
    "output": '{"ok": true}',
    "parsed": {"ok": True},
    "usage": {"input_tokens": 12, "output_tokens": 5},
    "cost": "0.000022",
    "model": "fake-chat",
    "attempts": 1,
    "request_id": "completion:00000000-0000-0000-0000-000000000000",
}
CANNED_MODELS: list[dict] = [
    {
        "provider": "fake",
        "model_id": "fake-chat",
        "display_name": "Fake chat (deterministic)",
        "supports_structured_output": True,
        "max_input_tokens": 32000,
        "input_price_per_1k": "0.001000",
        "output_price_per_1k": "0.002000",
    }
]


def error_response(
    status_code: int, code: str, message: str = "Toolbox error.", field_errors: dict | None = None
) -> httpx.Response:
    """A toolbox error body ``{"error", "message", "field_errors"?}``."""
    body: dict = {"error": code, "message": message}
    if field_errors is not None:
        body["field_errors"] = field_errors
    return httpx.Response(status_code, json=body)


@contextmanager
def mock_toolbox(channel_idx: str | None = None) -> Iterator[respx.MockRouter]:
    """Mock the completion API at the configured base URL; routes ``complete`` and ``models`` answer 200."""
    channel_idx = toolbox_settings.AI_TOOLBOX_CHANNEL if channel_idx is None else channel_idx
    prefix = f"{toolbox_settings.AI_TOOLBOX_BASE_URL.rstrip('/')}/api/ai-completion/v2/admin/{channel_idx}"
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{prefix}/complete/", name="complete").mock(
            return_value=httpx.Response(200, json=CANNED_COMPLETION)
        )
        router.get(f"{prefix}/models/", name="models").mock(return_value=httpx.Response(200, json=CANNED_MODELS))
        yield router
