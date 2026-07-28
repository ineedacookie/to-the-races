from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models

TAKEOVER_PRICE_INCREMENT_CENTS = 500


def migrate_seat_claims_forward(apps, schema_editor) -> None:
    RoundSeatClaim = apps.get_model("racing", "RoundSeatClaim")
    SeatOwnership = apps.get_model("racing", "SeatOwnership")
    RoundSeatMarket = apps.get_model("racing", "RoundSeatMarket")
    SeatTakeoverReceipt = apps.get_model("racing", "SeatTakeoverReceipt")
    Round = apps.get_model("racing", "Round")
    SpectatorSeatDefinition = apps.get_model("racing", "SpectatorSeatDefinition")

    for claim in RoundSeatClaim.objects.select_related("player", "seat", "round").order_by(
        "created_at",
        "pk",
    ):
        previous_receipt = (
            SeatTakeoverReceipt.objects.filter(seat_id=claim.seat_id)
            .order_by("-created_at", "-pk")
            .first()
        )
        receipt = SeatTakeoverReceipt.objects.create(
            player_id=claim.player_id,
            round_id=claim.round_id,
            seat_id=claim.seat_id,
            previous_owner_id=(
                previous_receipt.player_id if previous_receipt is not None else None
            ),
            price_paid_cents=claim.price_paid_cents,
            client_request_id=claim.client_request_id,
        )
        SeatTakeoverReceipt.objects.filter(pk=receipt.pk).update(created_at=claim.created_at)

    assigned_seat_ids: set[int] = set()
    assigned_player_ids: set[int] = set()
    for claim in RoundSeatClaim.objects.order_by("-created_at", "-pk"):
        if (
            claim.seat_id in assigned_seat_ids
            or claim.player_id in assigned_player_ids
        ):
            continue
        SeatOwnership.objects.create(
            seat_id=claim.seat_id,
            player_id=claim.player_id,
        )
        assigned_seat_ids.add(claim.seat_id)
        assigned_player_ids.add(claim.player_id)

    active_seats = list(
        SpectatorSeatDefinition.objects.filter(active=True).order_by("sort_order", "name", "pk")
    )
    open_round = Round.objects.filter(state="open").order_by("-number").first()
    if open_round is not None:
        for seat in active_seats:
            takeover_count = SeatTakeoverReceipt.objects.filter(
                round_id=open_round.pk,
                seat_id=seat.pk,
            ).count()
            RoundSeatMarket.objects.create(
                round_id=open_round.pk,
                seat_id=seat.pk,
                current_price_cents=seat.price_cents + takeover_count * TAKEOVER_PRICE_INCREMENT_CENTS,
                takeover_count=takeover_count,
            )


def migrate_seat_claims_backward(apps, schema_editor) -> None:
    RoundSeatClaim = apps.get_model("racing", "RoundSeatClaim")
    SeatTakeoverReceipt = apps.get_model("racing", "SeatTakeoverReceipt")

    restored_round_seats: set[tuple[int, int]] = set()
    restored_player_rounds: set[tuple[int, int]] = set()
    for receipt in SeatTakeoverReceipt.objects.order_by("-created_at", "-pk"):
        round_seat = (receipt.round_id, receipt.seat_id)
        player_round = (receipt.player_id, receipt.round_id)
        if round_seat in restored_round_seats or player_round in restored_player_rounds:
            continue
        claim = RoundSeatClaim.objects.create(
            player_id=receipt.player_id,
            round_id=receipt.round_id,
            seat_id=receipt.seat_id,
            price_paid_cents=receipt.price_paid_cents,
            client_request_id=receipt.client_request_id,
        )
        RoundSeatClaim.objects.filter(pk=claim.pk).update(created_at=receipt.created_at)
        restored_round_seats.add(round_seat)
        restored_player_rounds.add(player_round)


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0004_player_balance_non_negative"),
        ("racing", "0011_upgradeddefinition_playerupgrade"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeatOwnership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("acquired_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_ownership",
                        to="players.player",
                    ),
                ),
                (
                    "seat",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ownership",
                        to="racing.spectatorseatdefinition",
                    ),
                ),
            ],
            options={
                "ordering": ["acquired_at", "pk"],
            },
        ),
        migrations.CreateModel(
            name="RoundSeatMarket",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("current_price_cents", models.PositiveIntegerField()),
                ("takeover_count", models.PositiveIntegerField(default=0)),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_markets",
                        to="racing.round",
                    ),
                ),
                (
                    "seat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="round_markets",
                        to="racing.spectatorseatdefinition",
                    ),
                ),
            ],
            options={
                "ordering": ["seat__sort_order", "seat__name", "pk"],
            },
        ),
        migrations.CreateModel(
            name="SeatTakeoverReceipt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("price_paid_cents", models.PositiveIntegerField()),
                ("client_request_id", models.UUIDField(default=uuid.uuid4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_takeover_receipts",
                        to="players.player",
                    ),
                ),
                (
                    "previous_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="seat_takeover_evictions",
                        to="players.player",
                    ),
                ),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_takeover_receipts",
                        to="racing.round",
                    ),
                ),
                (
                    "seat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="takeover_receipts",
                        to="racing.spectatorseatdefinition",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="roundseatmarket",
            constraint=models.UniqueConstraint(
                fields=("round", "seat"),
                name="racing_unique_round_seat_market",
            ),
        ),
        migrations.AddConstraint(
            model_name="seattakeoverreceipt",
            constraint=models.UniqueConstraint(
                fields=("player", "client_request_id"),
                name="racing_unique_seat_takeover_player_request",
            ),
        ),
        migrations.RunPython(migrate_seat_claims_forward, migrate_seat_claims_backward),
        migrations.DeleteModel(
            name="RoundSeatClaim",
        ),
    ]
