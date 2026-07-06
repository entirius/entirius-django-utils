# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import Any

from django.http import JsonResponse

from .base_response import BaseResponse
from .errors import ErrorInfo


class Response(BaseResponse):
    language = None
    currency = None
    country = None

    def __init__(
        self,
        data: Any,
        status: str = "OK",
        message: str = "",
        status_code: int = 200,
        messages: list[str] | None = None,
        errors: list[ErrorInfo] = None,
    ):
        super().__init__(errors)
        self.data = data
        self.status = status
        self.message = message
        self.status_code = status_code

        if messages is None:
            messages = []

        self.messages = messages
        if message == "" and len(messages) > 0:
            self.message = messages[0]

    def add_regional(self, language: str | None = None, currency: str | None = None, country: str | None = None):
        self.language = language
        self.currency = currency
        self.country = country
        return self


class PaginatedResponse(Response):
    def __init__(
        self,
        pagination: dict,
        data: list,
        status: str = "OK",
        message: str = "",
        status_code: int = 200,
        messages: list[str] | None = None,
    ):
        super().__init__(data, status, message, status_code, messages)
        self.pagination = pagination


def to_json_response(res: Response):
    base = {
        "meta": {
            "status": res.status,
            "message": res.message,
            "messages": res.messages,
            "errors": [error.to_dict() for error in res.errors],
            "regional": {"language": res.language, "currency": res.currency, "country": res.country},
        },
        "data": res.data,
    }

    if isinstance(res, PaginatedResponse):
        body = dict(**base, pagination=res.pagination)
    else:
        body = base

    response = JsonResponse(body)
    response.status_code = res.status_code
    return response
