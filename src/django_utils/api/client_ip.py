# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Client IP resolution that cannot be spoofed through X-Forwarded-For.

``settings.CLIENT_IP_HEADER`` names a ``request.META`` key (e.g. ``"HTTP_CF_CONNECTING_IP"``). When set and
present, its value is the client IP. Trusting the header is only safe when the origin is reachable only through
the proxy that sets it (Cloudflare, an internal load balancer); otherwise any client can forge it.

Without the setting the DRF behaviour applies unchanged: ``BaseThrottle.get_ident`` honours ``NUM_PROXIES``.

Proxied storefront: when a storefront proxies ``/api/*`` server-side, every request reaches the API from the
storefront's IP. List that IP (or CIDR) in ``settings.CLIENT_IP_TRUSTED_PROXIES``; when the edge IP is inside it,
the visitor IP is read from ``settings.CLIENT_IP_FORWARDED_HEADER`` (default ``"HTTP_X_CLIENT_IP"``) if it holds a
valid IP address. The storefront must always overwrite that header. A malformed ``CLIENT_IP_TRUSTED_PROXIES`` entry
raises ``ImproperlyConfigured``. Empty list (default): the forwarded header is ignored.
"""

import ipaddress

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import BaseThrottle


def _edge_ip(request) -> str:
    header = getattr(settings, "CLIENT_IP_HEADER", None)
    if header and (value := request.META.get(header, "").strip()):
        return value
    return BaseThrottle().get_ident(request)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_trusted_proxy(ip: str) -> bool:
    address = _parse_ip(ip)
    if address is None:
        return False
    for entry in getattr(settings, "CLIENT_IP_TRUSTED_PROXIES", ()):
        try:
            network = ipaddress.ip_network(str(entry).strip(), strict=False)
        except ValueError as exc:
            raise ImproperlyConfigured(f"CLIENT_IP_TRUSTED_PROXIES: invalid entry {entry!r}") from exc
        if address.version == network.version and address in network:
            return True
    return False


def get_client_ip(request) -> str:
    """Return the client IP of a DRF Request or Django HttpRequest."""
    edge = _edge_ip(request)
    if not _is_trusted_proxy(edge):
        return edge
    forwarded_header = getattr(settings, "CLIENT_IP_FORWARDED_HEADER", "HTTP_X_CLIENT_IP")
    forwarded = request.META.get(forwarded_header, "").strip()
    return forwarded if _parse_ip(forwarded) else edge


class ClientIPThrottleMixin:
    """Mix into a DRF throttle: ``class X(ClientIPThrottleMixin, AnonRateThrottle)``."""

    def get_ident(self, request) -> str:
        return get_client_ip(request)
