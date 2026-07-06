# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from dataclasses import dataclass


@dataclass
class ErrorInfo:
    message: str
    code: str
    affected_values: list[str] | None = None
    affected_field: str | None = None
    extra: dict | None = None

    def to_dict(self):
        result = {"message": self.message, "code": self.code}
        if self.affected_values:
            result["affected_values"] = self.affected_values
        if self.affected_field:
            result["affected_field"] = self.affected_field
        if self.extra:
            result["extra"] = self.extra
        return result
