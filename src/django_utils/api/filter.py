# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import Any

from django.db.models import QuerySet
from django_filters.filterset import FilterSetMetaclass


def filter_qs(filterset: FilterSetMetaclass, params: dict, queryset: QuerySet, request=None) -> tuple[QuerySet, Any]:
    """
    Filters queryset according to request params

    Ex:
    qs = Model.objects.all()
    filtered_qs = filter_queryset(ModelFilter, request.GET, qs)
    """
    filter_obj = filterset(params, request=request, queryset=queryset)
    return filter_obj.qs, filter_obj
