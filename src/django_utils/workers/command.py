# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import importlib
from argparse import BooleanOptionalAction

from celery_once import AlreadyQueued
from django.core.management import BaseCommand
from django.utils import timezone


class ArgumentCommand(BaseCommand):
    default_arguments: list = []

    def get_module_method(self) -> tuple[str, str]:
        module_path = self.__module__.split(".")
        method_location = f"{module_path[0]}.tasks"
        method_name = module_path[-1].replace("-", "_")
        return method_location, method_name

    def _get_arguments(self, options) -> dict:
        args = {}
        for key in self.default_arguments:
            args[key] = options[key]
        return args

    def handle_arguments(self, options) -> dict:
        args = self._get_arguments(options)
        self.stdout.write("=====ARG=====")
        if len(args) > 0:
            for key, arg in args.items():
                self.stdout.write(f"{key}: {arg}")
            self.stdout.write("=============")
        else:
            self.stdout.write("--EMPTY--")
        return args

    def handle(self, *args, **options):
        arguments = self.handle_arguments(options)

        # Datetime when process was started
        arguments["runned_at"] = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M:%S.%f")
        runned_at = arguments["runned_at"]

        method_location, method_name = self.get_module_method()
        module = importlib.import_module(method_location)
        task = getattr(module, method_name)

        self.stdout.write(f"[{runned_at}] Running without celery.")
        task(**arguments)

        self.stdout.write(self.style.SUCCESS("DONE"))


class CeleryBaseCommand(ArgumentCommand):
    def add_arguments(self, parser):
        parser.add_argument("--celery", type=bool, action=BooleanOptionalAction, help="Run inside Celery tasks.")
        self.default_arguments.append("celery")

    def handle_arguments(self, options) -> tuple[bool, dict]:
        args = super().handle_arguments(options)
        celery = args.pop("celery")
        return celery, args

    def handle(self, *args, **options):
        celery, arguments = self.handle_arguments(options)

        # Datetime when process was started
        arguments["runned_at"] = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M:%S.%f")
        runned_at = arguments["runned_at"]
        self.stdout.write(f"[{runned_at}] Process started.")

        method_location, method_name = self.get_module_method()
        module = importlib.import_module(method_location)
        task = getattr(module, method_name)
        if celery:
            try:
                task.delay(*arguments)
                self.stdout.write(f"[{runned_at}] Task has been created.")
            except AlreadyQueued:
                self.stdout.write(f"[{runned_at}] Task was already queued.")
        else:
            self.stdout.write(f"[{runned_at}] Running without celery.")
            task(**arguments)

        ended_at = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M:%S.%f")
        self.stdout.write(f"[{ended_at}] Process ended.")
        self.stdout.write(self.style.SUCCESS("DONE"))


class ChannelBaseCommand(ArgumentCommand):
    def add_arguments(self, parser):
        parser.add_argument("--channel_idx", type=str, help="Volkanos Channel/Shop IDX")
        self.default_arguments.append("channel_idx")
        super().add_arguments(parser)


class ChannelCeleryCommand(CeleryBaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--channel_idx", type=str, help="Volkanos Channel/Shop IDX")
        self.default_arguments.append("channel_idx")
        super().add_arguments(parser)
