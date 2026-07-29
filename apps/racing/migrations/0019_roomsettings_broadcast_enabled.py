from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0018_alter_roomsettings_lineup_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomsettings",
            name="broadcast_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Show the live broadcast tab and load its video feed on betting devices."
                ),
                verbose_name="Enable Tune In broadcast",
            ),
        ),
        migrations.AlterField(
            model_name="roomsettings",
            name="betting_seconds",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text=(
                    "Minimum time betting stays open before the 15-second locked lineup. "
                    "Betting remains open longer when an active broadcast is still finishing."
                ),
                validators=[MinValueValidator(5), MaxValueValidator(300)],
                verbose_name="Pre-race betting period (seconds)",
            ),
        ),
    ]
