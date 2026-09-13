# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Toolbox availability for UIs — safe inside a request cycle: bounded, cached, never raises."""

import logging
from enum import StrEnum

from django.core.cache import cache

from django_utils.toolbox import settings as toolbox_settings
from django_utils.toolbox.client import ToolboxClient

logger = logging.getLogger(__name__)

CACHE_KEY = "django_utils.toolbox.status"
CACHE_TTL_S = 60
PROBE_TIMEOUT_S = 5.0


class ToolboxStatus(StrEnum):
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"
    UNREACHABLE = "unreachable"


def status() -> ToolboxStatus:
    """``unconfigured`` without network when a setting is empty; otherwise one cached ``GET models/`` probe."""
    settings_present = (
        toolbox_settings.AI_TOOLBOX_BASE_URL
        and toolbox_settings.AI_TOOLBOX_API_KEY
        and toolbox_settings.AI_TOOLBOX_CHANNEL
    )
    if not settings_present:
        return ToolboxStatus.UNCONFIGURED
    try:
        return _cached_probe()
    except Exception as exc:  # noqa: BLE001 — the cache backend itself may fail; status must not raise
        logger.warning("Toolbox status check failed: %s", type(exc).__name__)
        return ToolboxStatus.UNREACHABLE


def _cached_probe() -> ToolboxStatus:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return ToolboxStatus(cached)
    result = _probe()
    cache.set(CACHE_KEY, result.value, CACHE_TTL_S)
    return result


def _probe() -> ToolboxStatus:
    try:
        with ToolboxClient(max_retries=1) as client:
            client.list_models(timeout=PROBE_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 — any failure means "unreachable" for the UI
        logger.info("Toolbox unreachable: %s", type(exc).__name__)
        return ToolboxStatus.UNREACHABLE
    return ToolboxStatus.CONFIGURED
