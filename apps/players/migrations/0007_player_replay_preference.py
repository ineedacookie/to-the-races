from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0006_alter_player_balance_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="replay_preference",
            field=models.CharField(
                choices=[
                    ("ask", "Ask after each race"),
                    ("always_watch", "Always watch"),
                    ("always_skip", "Always skip"),
                ],
                default="ask",
                db_default="ask",
                max_length=16,
            ),
        ),
    ]
