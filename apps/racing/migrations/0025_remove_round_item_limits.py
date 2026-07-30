from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0024_add_invincibility_and_berserk_tonics"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="roomsettings",
            name="max_round_item_spend_cents",
        ),
        migrations.RemoveField(
            model_name="roomsettings",
            name="max_round_item_uses",
        ),
    ]
