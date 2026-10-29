# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Client IP resolution that cannot be spoofed through X-Forwarded-For.

``settings.CLIENT_IP_HEADER`` names a ``request.META`` key (e.g. ``"HTTP_CF_CONNECTING_IP"``). When set and
present, its value is the client IP. Trusting the header is only safe when the origin is reachable only through
the proxy that sets it (Cloudflare, an internal load balancer); otherwise any client can forge it.

Without the setting the DRF behaviour applies unchanged: ``BaseThrottle.get_ident`` honours ``NUM_PROXIES``.
"""

from django.conf import settings
from rest_framework.throttling import BaseThrottle


def get_client_ip(request) -> str:
    """Return the client IP of a DRF Request or Django HttpRequest."""
    header = getattr(settings, "CLIENT_IP_HEADER", None)
    if header and (value := request.META.get(header, "").strip()):
        return value
    return BaseThrottle().get_ident(request)


class ClientIPThrottleMixin:
    """Mix into a DRF throttle: ``class X(ClientIPThrottleMixin, AnonRateThrottle)``."""

    def get_ident(self, request) -> str:
        return get_client_ip(request)
