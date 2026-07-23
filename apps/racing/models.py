from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Self

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.players.models import Player


class RoomSettings(models.Model):
    singleton = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=60, default="To The Races")
    is_paused = models.BooleanField(default=False)
    betting_seconds = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(300)],
    )
    lineup_seconds = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
    )
    race_seconds = models.PositiveSmallIntegerField(
        default=120,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
    )
    results_seconds = models.PositiveSmallIntegerField(
        default=8,
        validators=[MinValueValidator(3), MaxValueValidator(120)],
    )
    opening_balance_cents = models.PositiveBigIntegerField(default=10_000)
    max_round_stake_cents = models.PositiveBigIntegerField(default=10_000)
    max_round_item_spend_cents = models.PositiveBigIntegerField(default=2_500)
    max_round_item_uses = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    runner_count = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(2), MaxValueValidator(8)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    @classmethod
    def load(cls) -> Self:
        settings, _created = cls.objects.get_or_create(pk=1)
        return settings


class Racer(models.Model):
    name = models.CharField(max_length=30, unique=True)
    slug = models.SlugField(max_length=36, unique=True)
    sprite_key = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=7, default="#f6c453")
    base_speed = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(1.5)],
    )
    resilience = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    recovery = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    aggression = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    chaos = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    default_odds = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("4.00"),
        validators=[MinValueValidator(Decimal("1.01")), MaxValueValidator(Decimal("99.99"))],
    )
    tagline = models.CharField(max_length=80, blank=True)
    backstory = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ItemDefinition(models.Model):
    class Kind(models.TextChoices):
        SPEED_TONIC = "speed_tonic", "Speed tonic"
        GUARD_TONIC = "guard_tonic", "Guard tonic"
        TRIP_TONIC = "trip_tonic", "Trip tonic"
        CONFUSION_TONIC = "confusion_tonic", "Confusion tonic"
        BANANA = "banana", "Banana"
        POTHOLE = "pothole", "Pothole"

    class Target(models.TextChoices):
        RACER = "racer", "Racer"
        TRACK = "track", "Track"

    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=24)
    color = models.CharField(max_length=7, default="#f6c453")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    target = models.CharField(max_length=10, choices=Target.choices)
    price_cents = models.PositiveIntegerField()
    effect_strength = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class SpectatorSeatDefinition(models.Model):
    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    sprite_key = models.CharField(max_length=40, default="slime")
    color = models.CharField(max_length=7, default="#f6c453")
    price_cents = models.PositiveIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Round(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Betting open"
        LOCKED = "locked", "Betting locked"
        RACING = "racing", "Race in progress"
        RESULTS = "results", "Showing results"

    number = models.PositiveIntegerField(unique=True)
    state = models.CharField(max_length=10, choices=State, default=State.OPEN)
    opened_at = models.DateTimeField()
    locks_at = models.DateTimeField()
    race_starts_at = models.DateTimeField()
    race_ends_at = models.DateTimeField()
    results_end_at = models.DateTimeField()
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]

    def __str__(self) -> str:
        return f"Round {self.number}"


class Race(models.Model):
    round = models.OneToOneField(Round, on_delete=models.CASCADE, related_name="race")
    seed = models.PositiveBigIntegerField(null=True, blank=True)
    tick_rate = models.PositiveSmallIntegerField(default=20)
    duration_ticks = models.PositiveIntegerField(default=0)
    inputs = models.JSONField(default=dict, blank=True)
    timeline = models.JSONField(default=list, blank=True)
    events = models.JSONField(default=list, blank=True)
    result = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Race for round {self.round.number}"


class RaceEntry(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="entries")
    racer = models.ForeignKey(Racer, on_delete=models.PROTECT, related_name="race_entries")
    lane = models.PositiveSmallIntegerField()
    odds = models.DecimalField(max_digits=5, decimal_places=2)
    finish_place = models.PositiveSmallIntegerField(null=True, blank=True)
    finish_tick = models.PositiveIntegerField(null=True, blank=True)
    dnf_reason = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["lane"]
        constraints = [
            models.UniqueConstraint(fields=["race", "racer"], name="racing_unique_racer"),
            models.UniqueConstraint(fields=["race", "lane"], name="racing_unique_lane"),
        ]

    def __str__(self) -> str:
        return f"{self.racer.name} in round {self.race.round.number}"


class RoundItemUse(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="item_uses")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="item_uses")
    item = models.ForeignKey(ItemDefinition, on_delete=models.PROTECT, related_name="uses")
    target_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.PROTECT,
        related_name="item_uses",
        null=True,
        blank=True,
    )
    track_lane = models.FloatField(null=True, blank=True)
    track_position = models.FloatField(null=True, blank=True)
    price_paid_cents = models.PositiveIntegerField()
    client_request_id = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "client_request_id"],
                name="racing_unique_item_player_request",
            ),
            models.UniqueConstraint(
                fields=["player", "round", "item"],
                name="racing_unique_item_once_per_round",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} used {self.item.name}"


class RoundSeatClaim(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="seat_claims")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="seat_claims")
    seat = models.ForeignKey(
        SpectatorSeatDefinition,
        on_delete=models.PROTECT,
        related_name="claims",
    )
    price_paid_cents = models.PositiveIntegerField()
    client_request_id = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "client_request_id"],
                name="racing_unique_seat_player_request",
            ),
            models.UniqueConstraint(
                fields=["round", "seat"],
                name="racing_unique_seat_per_round",
            ),
            models.UniqueConstraint(
                fields=["player", "round"],
                name="racing_unique_player_seat_per_round",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} claimed {self.seat.name}"
