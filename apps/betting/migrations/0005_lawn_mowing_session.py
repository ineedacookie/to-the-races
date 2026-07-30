import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("betting", "0004_alter_ledgerentry_kind_upgrade"),
    ]

    operations = [
        migrations.CreateModel(
            name="LawnMowingSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_request_id", models.UUIDField(default=uuid.uuid4)),
                ("mowed_cells", models.JSONField(default=list)),
                ("reward_credited", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lawn_mowing_sessions",
                        to="players.player",
                    ),
                ),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lawn_mowing_sessions",
                        to="racing.round",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="lawnmowingsession",
            constraint=models.UniqueConstraint(
                fields=("player", "round"),
                name="betting_unique_lawn_player_round",
            ),
        ),
        migrations.AddConstraint(
            model_name="lawnmowingsession",
            constraint=models.UniqueConstraint(
                fields=("player", "start_request_id"),
                name="betting_unique_lawn_start_request",
            ),
        ),
        migrations.AddIndex(
            model_name="lawnmowingsession",
            index=models.Index(fields=["round", "player"], name="betting_law_round_i_b6b769_idx"),
        ),
        migrations.AlterField(
            model_name="ledgerentry",
            name="kind",
            field=models.CharField(
                choices=[
                    ("opening", "Opening balance"),
                    ("stake", "Bet stake"),
                    ("payout", "Winning payout"),
                    ("refund", "Refund"),
                    ("adjustment", "Admin adjustment"),
                    ("item", "Item purchase"),
                    ("seat", "Seat claim"),
                    ("bailout", "Track medic bailout"),
                    ("lawn", "Lawn mowing"),
                    ("upgrade", "Permanent upgrade"),
                ],
                max_length=12,
            ),
        ),
    ]
