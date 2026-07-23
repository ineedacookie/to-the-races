from typing import Any

from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created, dispatch_uid="to_the_races.configure_sqlite")
def configure_sqlite(sender: Any, connection: Any, **kwargs: Any) -> None:
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
