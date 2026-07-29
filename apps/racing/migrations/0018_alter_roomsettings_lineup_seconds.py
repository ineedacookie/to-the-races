from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0017_seed_racer_world_records"),
    ]

    operations = [
        migrations.AlterField(
            model_name="roomsettings",
            name="lineup_seconds",
            field=models.PositiveSmallIntegerField(
                default=15,
                validators=[MinValueValidator(1), MaxValueValidator(30)],
            ),
        ),
    ]
