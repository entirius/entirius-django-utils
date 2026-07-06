# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import Any

from django.db import connections, models, transaction
from django.db.models import Case, Value, When
from django.db.models.functions import Cast


def partition(predicate, iterable):
    """Split iterable based on predicate - similar to itertools recipes."""
    trues = []
    falses = []
    for item in iterable:
        if predicate(item):
            trues.append(item)
        else:
            falses.append(item)
    return trues, falses


# used by:
# django-pricemanager PriceManager manager - Price model
# django-pim ProductManager, ProductAttributeManager manager - RealProduct, ProductAttribute, Product model
class EnhanceManager(models.Manager):
    """
    Enhanced manager with bulk_create and bulk_update supporting additional filters
    to prevent race conditions by applying filters atomically at SQL level.

    Usage example:
        # Update only records where updated_at < some_timestamp
        Product.objects.bulk_update(
            products,
            ['name', 'price'],
            filter_conditions={'updated_at__lt': timestamp}
        )

        # Create only if records don't exist with certain conditions
        RealProduct.objects.bulk_create(
            real_products,
            filter_conditions={'sku__in': existing_skus},
            ignore_conflicts=True
        )
    """

    def bulk_update(
        self,
        objs: list[models.Model],
        fields: list[str],
        batch_size: int | None = None,
        filter_conditions: dict[str, Any] | None = None,
    ) -> int:
        """
        Enhanced bulk_update with additional filter conditions applied atomically.

        Args:
            objs: List of model instances to update
            fields: List of field names to update
            batch_size: Number of objects to update per query
            filter_conditions: Additional filter conditions (e.g., {'updated_at__lt': value})
                              These conditions are applied in the WHERE clause to prevent race conditions

        Returns:
            Number of rows updated

        Example:
            # Update only products where updated_at hasn't changed since we fetched them
            Product.objects.bulk_update(
                products,
                ['name', 'price'],
                filter_conditions={'updated_at__lt': datetime.now()}
            )
        """
        if not objs:
            return 0
        if filter_conditions is None:
            # No additional conditions, use standard bulk_update
            return super().bulk_update(objs, fields, batch_size=batch_size)

        # Use custom implementation with filter conditions - based on Django's bulk_update
        return self._bulk_update_with_filters(objs, fields, batch_size, filter_conditions)

    def _bulk_update_with_filters(
        self,
        objs: list[models.Model],
        fields: list[str],
        batch_size: int | None,
        filter_conditions: dict[str, Any],
    ) -> int:
        """
        Internal method to perform bulk update with additional WHERE conditions.
        This is based on Django's original bulk_update but adds filter_conditions to WHERE clause.
        """
        if batch_size is not None and batch_size <= 0:
            raise ValueError("Batch size must be a positive integer.")
        if not fields:
            raise ValueError("Field names must be given to bulk_update().")
        objs = tuple(objs)
        if any(obj.pk is None for obj in objs):
            raise ValueError("All bulk_update() objects must have a primary key set.")

        # Convert field names to field objects
        fields = [self.model._meta.get_field(name) for name in fields]
        if any(not f.concrete or f.many_to_many for f in fields):
            raise ValueError("bulk_update() can only be used with concrete fields.")
        if any(f.primary_key for f in fields):
            raise ValueError("bulk_update() cannot be used with primary key fields.")
        if not objs:
            return 0

        for obj in objs:
            obj._prepare_related_fields_for_save(operation_name="bulk_update", fields=fields)

        # PK is used twice in the resulting update query, once in the filter
        # and once in the WHEN. Each field will also have one CAST.
        self._for_write = True
        connection = connections[self.db]
        max_batch_size = connection.ops.bulk_batch_size(["pk", "pk"] + fields, objs)
        batch_size = min(batch_size, max_batch_size) if batch_size else max_batch_size
        requires_casting = connection.features.requires_casted_case_in_updates
        batches = (objs[i : i + batch_size] for i in range(0, len(objs), batch_size))
        updates = []

        for batch_objs in batches:
            update_kwargs = {}
            for field in fields:
                when_statements = []
                for obj in batch_objs:
                    attr = getattr(obj, field.attname)
                    if not hasattr(attr, "resolve_expression"):
                        attr = Value(attr, output_field=field)
                    when_statements.append(When(pk=obj.pk, then=attr))
                case_statement = Case(*when_statements, output_field=field)
                if requires_casting:
                    case_statement = Cast(case_statement, output_field=field)
                update_kwargs[field.attname] = case_statement
            updates.append(([obj.pk for obj in batch_objs], update_kwargs))

        rows_updated = 0
        queryset = self.using(self.db)
        with transaction.atomic(using=self.db, savepoint=False):
            for pks, update_kwargs in updates:
                # THIS IS THE KEY DIFFERENCE: Add filter_conditions to the queryset
                filtered_qs = queryset.filter(pk__in=pks).filter(**filter_conditions)
                rows_updated += filtered_qs.update(**update_kwargs)

        return rows_updated
