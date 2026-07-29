from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def restore_mistaken_lineup_values(apps, _schema_editor) -> None:
    room_settings = apps.get_model("racing", "RoomSettings")
    room_settings.objects.filter(lineup_seconds=15).update(lineup_seconds=3)


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0019_roomsettings_broadcast_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="roomsettings",
            name="betting_seconds",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text=(
                    "Minimum time betting stays open. After a highlight show, betting "
                    "remains open for at least 15 additional seconds before the drinking "
                    "lineup."
                ),
                validators=[MinValueValidator(5), MaxValueValidator(300)],
                verbose_name="Pre-race betting period (seconds)",
            ),
        ),
        migrations.AlterField(
            model_name="roomsettings",
            name="lineup_seconds",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[MinValueValidator(1), MaxValueValidator(30)],
            ),
        ),
        migrations.RunPython(
            restore_mistaken_lineup_values,
            migrations.RunPython.noop,
        ),
    ]
