from __future__ import annotations

from collections.abc import Callable

from django.db import IntegrityError, models, transaction
from django.db.models import QuerySet


def existing_receipt[ModelT: models.Model, ReceiptT](
    queryset: QuerySet[ModelT],
    build_receipt: Callable[[ModelT], ReceiptT],
) -> ReceiptT | None:
    existing = queryset.first()
    return None if existing is None else build_receipt(existing)


def create_idempotently[ModelT: models.Model](
    *,
    create: Callable[[], ModelT],
    duplicate_queryset: Callable[[], QuerySet[ModelT]],
) -> tuple[ModelT, bool]:
    """Create inside a savepoint and recover a concurrent duplicate request."""

    try:
        with transaction.atomic():
            return create(), False
    except IntegrityError:
        duplicate = duplicate_queryset().first()
        if duplicate is None:
            raise
        return duplicate, True
