from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0014_expand_item_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="race",
            name="replay_montage",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
