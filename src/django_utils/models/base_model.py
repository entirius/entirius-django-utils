# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    # Powyższe kolumny dodadzą się na początku tabeli w DB
    # Aby sobie to zmienić należy po utworzeniu migracji edytować ją i
    # przenieść tworzenie tych kolumn na koniec. (estetyka)
    # Pamiętaj, że zmiana tego modelu spowołuje zmianę/migrację w innych modelach, które dziedziczą po BaseModel

    class Meta:
        abstract = True


class FinalModel(BaseModel):
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
