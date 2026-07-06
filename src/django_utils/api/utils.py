# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from django_utils import settings


# Need to have it here, otherwise django will iterate over a queryset
def make_media_url(media_path: str) -> str | None:
    media_url = getattr(settings, "MEDIA_URL", "")
    if media_path is not None:
        return "".join([media_url, media_path])
    else:
        return None
