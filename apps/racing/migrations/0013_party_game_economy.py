from django.db import migrations, models


def update_room_economy(apps, _schema_editor):
    room_settings = apps.get_model("racing", "RoomSettings")
    room_settings.objects.update(
        opening_balance_cents=20_000,
        max_round_stake_cents=15_000,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0012_persistent_seat_ownership"),
    ]

    operations = [
        migrations.AlterField(
            model_name="roomsettings",
            name="max_round_stake_cents",
            field=models.PositiveBigIntegerField(default=15_000),
        ),
        migrations.AlterField(
            model_name="roomsettings",
            name="opening_balance_cents",
            field=models.PositiveBigIntegerField(default=20_000),
        ),
        migrations.RunPython(update_room_economy, migrations.RunPython.noop),
    ]
