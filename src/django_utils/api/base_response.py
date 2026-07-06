# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from .errors import ErrorInfo


class BaseResponse:
    errors = None

    def __init__(self, errors: list[ErrorInfo] = None):
        self.errors = errors

        if errors is None:
            self.errors = []

    def add_error(
        self,
        message: str,
        code: str,
        affected_values: list[str] | None = None,
        affected_field: str | None = None,
        extra: dict | None = None,
    ):
        if code in [error.code for error in self.errors]:
            for error in self.errors:
                if error.code == code:
                    if affected_values:
                        error.affected_values = list(set(error.affected_values + affected_values))
                    break
        else:
            self.errors.append(ErrorInfo(message, code, affected_values, affected_field, extra))
        return self

    def add_errors(self, errors: list[ErrorInfo | dict]):
        for error in errors:
            if isinstance(error, ErrorInfo):
                self.add_error(error.message, error.code, error.affected_values, error.affected_field, error.extra)
            elif isinstance(error, dict):
                message = error.get("message", None)
                code = error.get("code", None)
                if isinstance(message, str) and isinstance(code, str):
                    self.add_error(message, code, error.get("affected_values", None))
            else:
                continue
        return self
