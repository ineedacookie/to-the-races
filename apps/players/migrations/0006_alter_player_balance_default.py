from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0005_reset_all_player_balances_to_100"),
    ]

    operations = [
        migrations.AlterField(
            model_name="player",
            name="balance_cents",
            field=models.BigIntegerField(default=20_000),
        ),
    ]
