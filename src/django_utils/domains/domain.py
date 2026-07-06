# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from abc import ABC
from datetime import datetime

from process_logger import ProcessLoggerMixin


class Domain(ProcessLoggerMixin, ABC):
    print_stages: bool = False

    def print(self, text):
        if self.print_stages:
            now = datetime.now().isoformat()
            print(f"[{now}] {str(text)}")
