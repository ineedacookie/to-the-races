from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0020_restore_lineup_duration"),
    ]

    operations = [
        migrations.AddField(
            model_name="round",
            name="broadcast_closed_at",
            field=models.DateTimeField(
                blank=True,
                editable=False,
                null=True,
            ),
        ),
    ]
