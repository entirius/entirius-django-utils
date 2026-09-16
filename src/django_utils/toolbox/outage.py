# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Dev/test-only outage switch: while it is on, every toolbox request fails as a refused connection.

Lets a BDD suite simulate "toolbox down" without stopping the toolbox. The flag lives in the Django cache, so
the service and its workers see the same state. It can exist only with `DEBUG` or `AI_TOOLBOX_TEST_SWITCH = True`,
never with `ENVIRONMENT == "production"`.
"""

import logging

from django.conf import settings
from django.core.cache import cache

from django_utils.toolbox import settings as toolbox_settings

logger = logging.getLogger(__name__)

CACHE_KEY = "django_utils.toolbox.outage"
# A forgotten switch heals itself: a failed test run must not leave a dev stack degraded for good.
OUTAGE_TTL_S = 900


class OutageSwitchDisabledError(Exception):
    """The switch is not available on this instance (no `DEBUG`, no `AI_TOOLBOX_TEST_SWITCH`, or production)."""


def allowed() -> bool:
    if getattr(settings, "ENVIRONMENT", "") == "production":
        return False
    return bool(settings.DEBUG or toolbox_settings.AI_TOOLBOX_TEST_SWITCH)


def is_down() -> bool:
    """True only while the switch is allowed and on; a failing cache reads as "not down", never raises."""
    if not allowed():
        return False
    try:
        return bool(cache.get(CACHE_KEY))
    except Exception as exc:  # noqa: BLE001 — the switch must never break a real request
        logger.warning("Toolbox outage switch unreadable: %s", type(exc).__name__)
        return False


def set_down(down: bool) -> None:
    """Turn the simulated outage on or off; the cached `status()` probe is dropped so it reflects the change."""
    from django_utils.toolbox.status import CACHE_KEY as STATUS_CACHE_KEY

    if not allowed():
        raise OutageSwitchDisabledError()
    if down:
        cache.set(CACHE_KEY, True, OUTAGE_TTL_S)
    else:
        cache.delete(CACHE_KEY)
    cache.delete(STATUS_CACHE_KEY)
