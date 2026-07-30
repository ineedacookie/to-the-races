import secrets

import apps.players.models
from django.db import migrations, models


def populate_api_keys(apps, schema_editor):
    player_model = apps.get_model("players", "Player")
    for player in player_model.objects.filter(api_key__isnull=True).iterator():
        player.api_key = f"ttr_{secrets.token_urlsafe(32)}"
        player.save(update_fields=["api_key"])


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0007_player_replay_preference"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="api_key",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.RunPython(populate_api_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="player",
            name="api_key",
            field=models.CharField(
                default=apps.players.models.generate_api_key,
                editable=False,
                max_length=64,
                unique=True,
            ),
        ),
    ]
