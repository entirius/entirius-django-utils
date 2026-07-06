# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from django.http import HttpRequest
from marshmallow.exceptions import MarshmallowError
from marshmallow.exceptions import ValidationError as MarshmallowValidationError

from ..settings import LOG_HTTP_CODE_GTE
from .base_response import BaseResponse
from .errors import ErrorInfo
from .responses import Response

logger = logging.getLogger(__name__)


class APIException(BaseResponse, Exception):
    data: dict = {}
    message: str = "Error"
    status: str = "ERR"
    status_code: int = 500

    def __init__(self, data=None, message=None, status=None, errors: list[ErrorInfo] = None) -> None:
        if errors is None:
            errors = []
        super().__init__(errors)
        self.data = self.data if data is None else data
        self.message = self.message if message is None else message
        self.status = self.status if status is None else status

    def __str__(self) -> str:
        return f"{self.status}: {self.message}"


class BadRequest(APIException):
    message = "Invalid request"
    status = "BAD_REQUEST"
    status_code = 400


class EmailTaken(BadRequest):
    message = "Email already in use"
    status = "EMAIL_TAKEN"


class ValidationError(BadRequest):
    message = "Validation Error"


class Unauthorized(APIException):
    message = "Requires authentication"
    status = "UNAUTHORIZED"
    status_code = 401


class JWTException(Unauthorized):
    def __init__(self, message, status, code):
        self.message = message
        self.status = status
        self.code = code


class Forbidden(APIException):
    message = "Permission denied"
    status = "FORBIDDEN"
    status_code = 403


class NotFound(APIException):
    message = "Resource not found"
    status = "NOT_FOUND"
    status_code = 404


class MethodNotAllowed(APIException):
    message = "Invalid http method"
    status = "METHOD_NOT_ALLOWED"
    status_code = 405


def handle_django_exception(e): ...


def handle_marshmallow_exception(e):
    def normalize(e):
        if isinstance(e, MarshmallowValidationError):
            return normalize(e.normalized_messages())
        elif isinstance(e, dict):
            return {key: normalize(elem) for key, elem in e.items()}
        elif isinstance(e, list):
            return [normalize(elem) for elem in e]
        else:
            return e

    if isinstance(e, MarshmallowValidationError):
        status = "BAD_REQUEST"
        status_code = 400
        message = "Validation error"
        data = normalize(e)
    else:
        status = "ERR"
        status_code = 500
        message = "Unhandeld Validaion Exception"
        data = {}

    return status, status_code, message, data


def handle_exception(e: Exception, request: HttpRequest):
    if isinstance(e, APIException):
        status = e.status
        status_code = e.status_code
        message = e.message
        data = e.data
        errors = e.errors
    elif isinstance(e, MarshmallowError):
        errors = []
        status, status_code, message, data = handle_marshmallow_exception(e)
    else:
        errors = []
        status = "ERR"
        status_code = 500
        message = "Internal Exception"
        data = {}

    if status_code >= LOG_HTTP_CODE_GTE:
        # logger.exception is better for sentry than logger.error
        logger.exception(e)

    return Response(status=status, status_code=status_code, message=message, data=data, errors=errors)
