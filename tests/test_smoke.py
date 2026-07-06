# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Smoke test: every public submodule imports cleanly under a configured Django."""

import importlib

import pytest

MODULES = [
    "django_utils.admin.base_admin",
    "django_utils.api.base_response",
    "django_utils.api.decorators",
    "django_utils.api.errors",
    "django_utils.api.exceptions",
    "django_utils.api.filter",
    "django_utils.api.pagination",
    "django_utils.api.responses",
    "django_utils.api.utils",
    "django_utils.api.v2_errors",
    "django_utils.domains.domain",
    "django_utils.json.encoder",
    "django_utils.managers.enhance_manager",
    "django_utils.models.base_model",
    "django_utils.settings",
    "django_utils.tools.t9n",
    "django_utils.tools.text",
    "django_utils.workers.command",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    assert importlib.import_module(module)
