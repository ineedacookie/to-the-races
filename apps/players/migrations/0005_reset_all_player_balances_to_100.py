from django.db import migrations

RESET_BALANCE_CENTS = 10_000


def reset_all_player_balances(apps, _schema_editor):
    player = apps.get_model("players", "Player")
    player.objects.all().update(balance_cents=RESET_BALANCE_CENTS)


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0004_player_balance_non_negative"),
    ]

    operations = [
        migrations.RunPython(reset_all_player_balances, migrations.RunPython.noop),
    ]
