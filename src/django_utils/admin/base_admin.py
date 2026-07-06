# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from django_utils.settings import ADMIN_THEME

logger = logging.getLogger(__name__)

match ADMIN_THEME:
    case "unfold":
        try:
            from unfold.admin import ModelAdmin, StackedInline, TabularInline
        except ImportError:
            logger.error("Unfold admin theme is not installed, run: pip install django-unfold")
            from django.contrib.admin import ModelAdmin, StackedInline, TabularInline
    case _:
        from django.contrib.admin import ModelAdmin, StackedInline, TabularInline


class BaseModelAdmin(ModelAdmin):
    pass


class BaseStackedInline(StackedInline):
    pass


class BaseTabularInline(TabularInline):
    pass
