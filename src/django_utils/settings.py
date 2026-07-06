# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.conf import settings

MEDIA_URL = getattr(settings, "MEDIA_URL", "")
HEADER_IP_ADDRESS = getattr(settings, "HEADER_IP_ADDRESS", "X-Forwarded-For")
HEADER_COUNTRY = getattr(settings, "HEADER_COUNTRY", "CF-IPCountry")

LOG_HTTP_CODE_GTE = getattr(settings, "LOG_HTTP_CODE_GTE", 400)

ADMIN_THEME = getattr(settings, "ADMIN_THEME", None)
