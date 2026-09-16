# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Toolbox client settings, read lazily from Django settings on every attribute access.

Required in service settings_local.py:
    AI_TOOLBOX_BASE_URL = "https://ai-toolbox.internal:8000"
    AI_TOOLBOX_API_KEY = "<toolbox API key>"
    AI_TOOLBOX_CHANNEL = "<toolbox channel idx>"

``from django_utils.toolbox.settings import AI_TOOLBOX_BASE_URL`` still works, but binds the value at
import time — call sites that must honour ``override_settings`` read ``settings.AI_TOOLBOX_BASE_URL``
through the module instead.
"""

from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    "AI_TOOLBOX_BASE_URL": "",
    "AI_TOOLBOX_API_KEY": "",
    "AI_TOOLBOX_CHANNEL": "",
    "AI_TOOLBOX_TIMEOUT": 60.0,
    "AI_COMPLETION_TIMEOUT": 130.0,
    "AI_TOOLBOX_MAX_RETRIES": 3,
    "AI_TOOLBOX_TEST_SWITCH": False,
}


def __getattr__(name: str) -> Any:
    if name not in DEFAULTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(settings, name, DEFAULTS[name])
