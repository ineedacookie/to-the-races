from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

from apps.players.models import Player
from apps.racing.models import RaceEntry, Round


class BailoutSession(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="bailout_sessions")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="bailout_sessions")
    race_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.PROTECT,
        related_name="bailout_sessions",
    )
    start_request_id = models.UUIDField(default=uuid.uuid4)
    wound_count = models.PositiveSmallIntegerField()
    wounds = models.JSONField()
    reward_credited = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "round"],
                name="betting_unique_bailout_player_round",
            ),
            models.UniqueConstraint(
                fields=["player", "start_request_id"],
                name="betting_unique_bailout_start_request",
            ),
            models.CheckConstraint(
                condition=models.Q(wound_count__gte=2) & models.Q(wound_count__lte=5),
                name="betting_bailout_wound_count_bounds",
            ),
        ]
        indexes = [
            models.Index(fields=["round", "player"]),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} bailout round {self.round.number}"


class BailoutPatch(models.Model):
    session = models.ForeignKey(
        BailoutSession,
        on_delete=models.CASCADE,
        related_name="patches",
    )
    wound_index = models.PositiveSmallIntegerField()
    patch_request_id = models.UUIDField(default=uuid.uuid4)
    patched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["patched_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "wound_index"],
                name="betting_unique_bailout_wound_index",
            ),
            models.UniqueConstraint(
                fields=["session", "patch_request_id"],
                name="betting_unique_bailout_patch_request",
            ),
        ]

    def __str__(self) -> str:
        return f"Patch {self.wound_index} on bailout {self.session_id}"


class LawnMowingSession(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="lawn_mowing_sessions",
    )
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="lawn_mowing_sessions",
    )
    start_request_id = models.UUIDField(default=uuid.uuid4)
    mowed_cells = models.JSONField(default=list)
    reward_credited = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "round"],
                name="betting_unique_lawn_player_round",
            ),
            models.UniqueConstraint(
                fields=["player", "start_request_id"],
                name="betting_unique_lawn_start_request",
            ),
        ]
        indexes = [models.Index(fields=["round", "player"])]

    def __str__(self) -> str:
        return f"{self.player.nickname} lawn round {self.round.number}"


class Bet(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        VOID = "void", "Void"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="bets")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="bets")
    race_entry = models.ForeignKey(RaceEntry, on_delete=models.PROTECT, related_name="bets")
    client_request_id = models.UUIDField(default=uuid.uuid4)
    amount_cents = models.PositiveBigIntegerField()
    decimal_odds = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    payout_cents = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "client_request_id"],
                name="betting_unique_player_request",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_cents__gt=0),
                name="betting_positive_stake",
            ),
            models.CheckConstraint(
                condition=models.Q(decimal_odds__gte=Decimal("1.01")),
                name="betting_valid_odds",
            ),
        ]
        indexes = [
            models.Index(fields=["round", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname}: {self.amount_cents} on {self.race_entry.racer.name}"


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        OPENING = "opening", "Opening balance"
        STAKE = "stake", "Bet stake"
        PAYOUT = "payout", "Winning payout"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Admin adjustment"
        ITEM = "item", "Item purchase"
        SEAT = "seat", "Seat claim"
        BAILOUT = "bailout", "Track medic bailout"
        LAWN = "lawn", "Lawn mowing"
        UPGRADE = "upgrade", "Permanent upgrade"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="ledger_entries")
    round = models.ForeignKey(
        Round,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    bet = models.ForeignKey(
        Bet,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=12, choices=Kind)
    amount_cents = models.BigIntegerField()
    balance_after_cents = models.BigIntegerField()
    description = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["player", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname}: {self.amount_cents:+} cents"
