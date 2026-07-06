# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import ipaddress
import logging
from functools import partial, wraps

from django.contrib import auth
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django_regional.models import Country
from webargs.djangoparser import use_args

from django_utils import settings
from django_utils.api.exceptions import JWTException

from .exceptions import MethodNotAllowed, Unauthorized, handle_exception
from .responses import PaginatedResponse, Response, to_json_response

logger = logging.getLogger(__name__)


def api_view(view):
    """
    Wraps view function or method on a class based view,
    enforcing standard response formatting and exception handling.

    Decorated function must return a Response object.
    Response class can be found in helpers/response.py
    """

    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except Exception as e:
            response = handle_exception(e, request)
        finally:
            if isinstance(response, (Response, PaginatedResponse)):
                return to_json_response(response)
            elif isinstance(response, HttpResponseRedirect):
                return response
            elif isinstance(response, HttpResponse):
                return response
            else:
                JsonResponse({"error": "view returned unsupported response type"})

    return _wrapped


def authenticate_optional(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        try:
            request.user = auth.authenticate(request)
        except JWTException:
            request.user = None
            pass

        response = view(request, *args, **kwargs)
        return response

    return _wrapped


def authenticate(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        request.user = auth.authenticate(request)
        request.customer = request.user.customer if request.user is not None else None
        response = view(request, *args, **kwargs)
        return response

    return _wrapped


def require_authentication(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        passed = user is not None and user.is_authenticated
        if passed:
            result = view(request, *args, **kwargs)
            return result
        else:
            raise Unauthorized

    return _wrapped


def require_http_method(*methods):
    def _wrapper(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            passed = request.method in methods
            if passed:
                result = view(request, *args, **kwargs)
                return result
            else:
                raise MethodNotAllowed

        return _wrapped

    return _wrapper


def ip_getter(view_func):
    """
    Dekorator, który pobiera adres IP z nagłówka i zapisuje go do request.ip.
    Domyślnie sprawdza nagłówek X-Forwarded-For, a następnie X-Real-IP.
    Jeśli nie ma tych nagłówków, używa request.META.get('REMOTE_ADDR').
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Próba pobrania IP z różnych nagłówków HTTP
        if (last_session_ip := request.headers.get(settings.HEADER_IP_ADDRESS, None)) is not None:
            try:
                ipaddress.ip_address(last_session_ip)
                request.last_session_ip = last_session_ip
            except ValueError:
                logger.warning(f"IP address {last_session_ip} is not valid")

        response = view_func(request, *args, **kwargs)
        return response

    return _wrapped_view


def save_ip_and_country(view_func):
    """

    request needs to have headers with keys:
    - settings.HEADER_IP_ADDRESS
    - settings.HEADER_COUNTRY

    and customer object in request.customer

    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        customer = request.customer
        if not customer:
            return response

        if (last_session_ip := request.headers.get(settings.HEADER_IP_ADDRESS, None)) is not None:
            try:
                ipaddress.ip_address(last_session_ip)
                customer.last_session_ip = last_session_ip
            except ValueError:
                logger.warning(f"IP address {last_session_ip} for customer {customer.uid} is not valid")

        if (last_session_country := request.headers.get(settings.HEADER_COUNTRY, None)) is not None:
            try:
                country = Country.objects.get(iso2=last_session_country)
                customer.last_session_country = country
            except ObjectDoesNotExist:
                logger.warning(f"Country {last_session_country} for customer {customer.uid} is not valid")
        try:
            customer.save()
        except Exception as e:
            logger.error(f"Failed to save customer {customer.uid} last session data: {e}")
        return response

    return _wrapped_view


def verify_captcha(view_func):
    try:
        from django_captcha.output.decorators import verify_recaptcha
    except ImportError:
        return view_func

    return verify_recaptcha(view_func)


# Uses webargs django parser
# BASICS https://webargs.readthedocs.io/en/latest/quickstart.html#basic-usage
# MODULE API https://webargs.readthedocs.io/en/latest/api.html#module-webargs.djangoparser
# HOW TO USE WHAT'S BELOW https://webargs.readthedocs.io/en/latest/advanced.html#mixing-locations
# HOW TO USE WITH DATACLASSES https://github.com/lovasoa/marshmallow_dataclass
# TODO Think about autodocs with apispec and apispec-decorator-crawler
parse_body = partial(use_args, location="json")
parse_form = partial(use_args, location="form")
parse_parameters = partial(use_args, location="query")
