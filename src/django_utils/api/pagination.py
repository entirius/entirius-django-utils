# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from django.core.paginator import Paginator
from django.db.models import QuerySet

from .exceptions import BadRequest


def paginate_qs(params: dict, objs_list: QuerySet) -> tuple[dict, QuerySet]:
    """
    Paginates list or queryset according to request params

    Ex:
    qs = Model.objects.all()
    pagination, paginated_qs = paginate(request.GET, qs)
    """
    page_param = params.get("page", None)
    which_page = int(page_param) if page_param is not None else 1
    limit_param = params.get("limit", None)
    objs_per_page = int(limit_param) if limit_param is not None else 10
    if objs_per_page > 100:
        raise BadRequest(message="Requesting more than 100 records per request is not allowed")
    else:
        paginator = Paginator(objs_list, objs_per_page)
        pages = paginator.num_pages
        records = paginator.count
        pagination_dict = {
            "page": which_page,
            "limit": objs_per_page,
            "pages": pages,
            "records": records,
        }
        page = paginator.page(which_page)
        return pagination_dict, page.object_list
