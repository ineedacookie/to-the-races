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
    broadcast_enabled = models.BooleanField(
        default=True,
        verbose_name="Enable Tune In broadcast",
        help_text="Show the live broadcast tab and load its video feed on betting devices.",
    )
    betting_seconds = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Pre-race betting period (seconds)",
        help_text=(
            "Minimum time betting stays open. After a highlight show, betting remains "
            "open for at least 15 additional seconds before the drinking lineup."
        ),
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
    opening_balance_cents = models.PositiveBigIntegerField(default=20_000)
    max_round_stake_cents = models.PositiveBigIntegerField(default=15_000)
    max_inventory_items = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    max_round_item_spend_cents = models.PositiveBigIntegerField(default=25_000)
    max_round_item_uses = models.PositiveSmallIntegerField(
        default=4,
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
        GROWTH_TONIC = "growth_tonic", "Growth tonic"
        SHRINK_TONIC = "shrink_tonic", "Shrink tonic"
        TRANSFORM_TONIC = "transform_tonic", "Transform tonic"
        FIREPROOF_TONIC = "fireproof_tonic", "Fireproof tonic"
        NITRO_SERUM = "nitro_serum", "Nitro serum"
        RECOVERY_BREW = "recovery_brew", "Recovery brew"
        GHOST_DRAUGHT = "ghost_draught", "Ghost draught"
        SECOND_WIND = "second_wind", "Second wind"
        PHOENIX_FLASK = "phoenix_flask", "Phoenix flask"
        INVINCIBILITY_TONIC = "invincibility_tonic", "Invincibility tonic"
        BERSERK_TONIC = "berserk_tonic", "Berserk tonic"
        BANANA = "banana", "Banana"
        POTHOLE = "pothole", "Pothole"
        OIL_SLICK = "oil_slick", "Oil slick"
        BOOST_PAD = "boost_pad", "Boost pad"
        BOXING_GLOVE = "boxing_glove", "Boxing glove"
        DETOUR_SIGN = "detour_sign", "Detour sign"
        SPEED_BUMP = "speed_bump", "Speed bump"
        STOP_SIGN = "stop_sign", "Stop sign"
        GLASS_DOOR = "glass_door", "Glass door"
        ROCK_WALL = "rock_wall", "Rock wall"
        ROOMBA_VACUUM = "roomba_vacuum", "Roomba vacuum"
        SPRINGBOARD = "springboard", "Springboard"
        MAGNET_MINE = "magnet_mine", "Magnet mine"
        PORTAL_GATE = "portal_gate", "Portal gate"

    class Target(models.TextChoices):
        RACER = "racer", "Racer"
        TRACK = "track", "Track"

    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=24)
    color = models.CharField(max_length=7, default="#f6c453")
    kind = models.CharField(max_length=24, choices=Kind.choices)
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


class UpgradeDefinition(models.Model):
    class Kind(models.TextChoices):
        INVENTORY_CAPACITY = "inventory_capacity", "Inventory capacity"

    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    inventory_capacity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    price_cents = models.PositiveIntegerField()
    prerequisite = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successors",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class PlayerUpgrade(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="upgrades")
    upgrade = models.ForeignKey(
        UpgradeDefinition,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    price_paid_cents = models.PositiveIntegerField()
    purchase_request_id = models.UUIDField(default=uuid.uuid4)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["purchased_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "upgrade"],
                name="racing_unique_player_upgrade",
            ),
            models.UniqueConstraint(
                fields=["player", "purchase_request_id"],
                name="racing_unique_upgrade_purchase_request",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} owns {self.upgrade.name}"


class SpectatorSeatDefinition(models.Model):
    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    sprite_key = models.CharField(max_length=40, default="slime")
    color = models.CharField(max_length=7, default="#f6c453")
    price_cents = models.PositiveIntegerField()
    payout_bonus_bps = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(5_000)],
    )
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
    broadcast_closed_at = models.DateTimeField(null=True, blank=True, editable=False)
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
    replay_montage = models.JSONField(default=dict, blank=True)
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


class RacerWorldRecord(models.Model):
    class Metric(models.TextChoices):
        FASTEST_FINISH = "fastest_finish", "Fastest official finish"
        MOST_FALLS = "most_falls", "Most falls in one race"
        LONGEST_CRAWL = "longest_crawl", "Longest crawl in one race"
        MOST_WRONG_WAY = "most_wrong_way", "Most wrong-way episodes"
        MOST_RECOVERIES = "most_recoveries", "Most recoveries"
        MOST_SHOWBOATS = "most_showboats", "Most showboats"

    metric = models.CharField(max_length=24, choices=Metric.choices, unique=True)
    racer = models.ForeignKey(
        Racer,
        on_delete=models.PROTECT,
        related_name="world_records",
    )
    round = models.ForeignKey(
        Round,
        on_delete=models.PROTECT,
        related_name="world_records",
    )
    race_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.PROTECT,
        related_name="world_records",
    )
    value = models.PositiveBigIntegerField()
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["metric"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__gt=0),
                name="racing_world_record_positive_value",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_metric_display()}: {self.racer.name}"


class InventoryItem(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="inventory_items")
    item = models.ForeignKey(
        ItemDefinition,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    price_paid_cents = models.PositiveIntegerField()
    purchase_request_id = models.UUIDField(default=uuid.uuid4)
    purchased_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    discarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["purchased_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "purchase_request_id"],
                name="racing_unique_inventory_purchase_request",
            ),
        ]
        indexes = [
            models.Index(fields=["player", "used_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} owns {self.item.name}"


class RoundItemUse(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="item_uses")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="item_uses")
    item = models.ForeignKey(ItemDefinition, on_delete=models.PROTECT, related_name="uses")
    inventory_item = models.OneToOneField(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="round_use",
        null=True,
        blank=True,
    )
    target_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.PROTECT,
        related_name="item_uses",
        null=True,
        blank=True,
    )
    track_lane = models.FloatField(null=True, blank=True)
    track_position = models.FloatField(null=True, blank=True)
    activation_tick = models.PositiveIntegerField(default=0)
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
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} used {self.item.name}"


class SeatOwnership(models.Model):
    seat = models.OneToOneField(
        SpectatorSeatDefinition,
        on_delete=models.CASCADE,
        related_name="ownership",
    )
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name="seat_ownership",
    )
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["acquired_at", "pk"]

    def __str__(self) -> str:
        return f"{self.player.nickname} owns {self.seat.name}"


class RoundSeatMarket(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="seat_markets")
    seat = models.ForeignKey(
        SpectatorSeatDefinition,
        on_delete=models.PROTECT,
        related_name="round_markets",
    )
    current_price_cents = models.PositiveIntegerField()
    takeover_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["seat__sort_order", "seat__name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "seat"],
                name="racing_unique_round_seat_market",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.seat.name} market for round {self.round.number}"


class SeatTakeoverReceipt(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="seat_takeover_receipts",
    )
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="seat_takeover_receipts",
    )
    seat = models.ForeignKey(
        SpectatorSeatDefinition,
        on_delete=models.PROTECT,
        related_name="takeover_receipts",
    )
    previous_owner = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        related_name="seat_takeover_evictions",
        null=True,
        blank=True,
    )
    price_paid_cents = models.PositiveIntegerField()
    client_request_id = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "client_request_id"],
                name="racing_unique_seat_takeover_player_request",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player.nickname} took {self.seat.name}"


class RoundDiscount(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="discounts")
    item = models.ForeignKey(
        ItemDefinition,
        on_delete=models.PROTECT,
        related_name="round_discounts",
    )
    discount_pct = models.PositiveIntegerField(
        help_text="Discount percentage (20-90).",
    )

    class Meta:
        ordering = ["item__sort_order", "item__name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "item"],
                name="racing_unique_round_discount",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.discount_pct}% off {self.item.name} in round {self.round.number}"
