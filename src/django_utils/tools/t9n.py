# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import base64
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup

from .text import generate_url_key


@dataclass
class DTO:
    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class T9N(DTO):
    locale: str
    value: str | list[str]

    def is_value_list(self) -> bool:
        return isinstance(self.value, list)


class T9NCollection(dict):
    def add(self, t9n: T9N):
        self[t9n.locale] = t9n

    def check_if_all_locales_exists(self, locales: list[str]) -> bool:
        return all([locale in self.keys() for locale in locales])

    def asdict(self, locales: list[str] | None = None) -> dict:
        if locales is None:
            return {k: v.value for k, v in self.items()}
        return {k: v.value for k, v in self.items() if k in locales}

    def asdict_converted_base64(
        self, locales: list[str] | None = None, cleanup_html: bool = False, logger=None
    ) -> dict:
        def decode_base64(value: str) -> str:
            return base64.b64decode(value).decode("utf-8")

        def clear_html(value: str) -> str:
            if not cleanup_html:
                return value
            try:
                # Parse the HTML
                soup = BeautifulSoup(value, "html.parser")

                # Remove all class attributes
                for tag in soup.find_all(class_=True):
                    del tag["class"]

                return str(soup)
            except Exception:
                if logger:
                    logger.set_code(None)
                    logger.error("Error while cleaning HTML")
                return value

        def clear_carret(value: str) -> str:
            return value.replace("\n", "").replace("\r", "")

        if locales is None:
            return {k: clear_carret(clear_html(decode_base64(v.value))) for k, v in self.items()}
        return {k: clear_carret(clear_html(decode_base64(v.value))) for k, v in self.items() if k in locales}

    @staticmethod
    def factory(data: list) -> "T9NCollection":
        col = T9NCollection()
        for d in data:
            locale = d.get("locale", None)
            value = d.get("value", None)
            if locale and value:
                col.add(T9N(locale=locale, value=value))
        return col


class T9NCollectionNames(T9NCollection):
    def generate_url_keys(
        self, locales: list[str], idx: str | None = None, append_idx=False, max_length: int = 200
    ) -> dict[str, str]:
        url_keys = {}
        for locale, t9n in self.items():
            if locale not in locales:
                continue

            url_keys[locale] = generate_url_key(t9n.value, idx, append_idx, max_length)

        return url_keys

    @staticmethod
    def factory(data: list) -> "T9NCollectionNames":
        col = T9NCollectionNames()
        for d in data:
            locale = d.get("locale", None)
            value = d.get("value", None)
            if locale and value:
                col.add(T9N(locale=locale, value=value))
        return col
