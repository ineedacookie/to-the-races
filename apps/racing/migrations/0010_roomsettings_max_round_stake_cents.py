from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("racing", "0009_remove_roomsettings_max_round_stake_cents_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomsettings",
            name="max_round_stake_cents",
            field=models.PositiveBigIntegerField(default=50_000),
        ),
    ]
