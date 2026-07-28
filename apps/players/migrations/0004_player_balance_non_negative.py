from django.db import migrations, models


def reset_negative_balances(apps, _schema_editor):
    player = apps.get_model("players", "Player")
    player.objects.filter(balance_cents__lt=0).update(balance_cents=0)


class Migration(migrations.Migration):

    dependencies = [
        ("players", "0003_remove_player_device_device_player"),
    ]

    operations = [
        migrations.RunPython(reset_negative_balances, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="player",
            constraint=models.CheckConstraint(
                condition=models.Q(balance_cents__gte=0),
                name="players_balance_non_negative",
            ),
        ),
    ]
