from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.racing.models import (
    InventoryItem,
    ItemDefinition,
    PlayerUpgrade,
    Race,
    RaceEntry,
    Racer,
    RoomSettings,
    Round,
    RoundItemUse,
    RoundSeatMarket,
    SeatOwnership,
    SeatTakeoverReceipt,
    SpectatorSeatDefinition,
    UpgradeDefinition,
)


@admin.register(RoomSettings)
class RoomSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Game",
            {
                "fields": ("name", "is_paused", "runner_count"),
            },
        ),
        (
            "Round timing",
            {
                "fields": (
                    "betting_seconds",
                    "lineup_seconds",
                    "race_seconds",
                    "results_seconds",
                ),
            },
        ),
        (
            "Fun money",
            {
                "fields": (
                    "opening_balance_cents",
                    "max_round_stake_cents",
                    "max_inventory_items",
                    "max_round_item_spend_cents",
                    "max_round_item_uses",
                ),
            },
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return not RoomSettings.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: RoomSettings | None = None) -> bool:
        return False


@admin.register(Racer)
class RacerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sprite_key",
        "tagline",
        "default_odds",
        "base_speed",
        "resilience",
        "recovery",
        "aggression",
        "chaos",
        "active",
    )
    list_editable = (
        "default_odds",
        "base_speed",
        "resilience",
        "recovery",
        "aggression",
        "chaos",
        "active",
    )
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ItemDefinition)
class ItemDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "kind",
        "target",
        "price_cents",
        "effect_strength",
        "active",
        "sort_order",
    )
    list_editable = ("price_cents", "effect_strength", "active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(UpgradeDefinition)
class UpgradeDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "kind",
        "inventory_capacity",
        "price_cents",
        "prerequisite",
        "active",
        "sort_order",
    )
    list_editable = ("price_cents", "inventory_capacity", "active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PlayerUpgrade)
class PlayerUpgradeAdmin(admin.ModelAdmin):
    list_display = ("player", "upgrade", "price_paid_cents", "purchased_at")
    readonly_fields = (
        "player",
        "upgrade",
        "price_paid_cents",
        "purchase_request_id",
        "purchased_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: PlayerUpgrade | None = None,
    ) -> bool:
        return False


@admin.register(SpectatorSeatDefinition)
class SpectatorSeatDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "sprite_key",
        "price_cents",
        "payout_bonus_bps",
        "color",
        "active",
        "sort_order",
    )
    list_editable = (
        "sprite_key",
        "price_cents",
        "payout_bonus_bps",
        "color",
        "active",
        "sort_order",
    )
    prepopulated_fields = {"slug": ("name",)}


class RoundItemUseInline(admin.TabularInline):
    model = RoundItemUse
    extra = 0
    readonly_fields = (
        "player",
        "item",
        "inventory_item",
        "target_entry",
        "track_lane",
        "track_position",
        "activation_tick",
        "price_paid_cents",
        "client_request_id",
        "created_at",
    )
    can_delete = False


class RoundSeatMarketInline(admin.TabularInline):
    model = RoundSeatMarket
    extra = 0
    readonly_fields = (
        "seat",
        "current_price_cents",
        "takeover_count",
    )
    can_delete = False


class SeatTakeoverReceiptInline(admin.TabularInline):
    model = SeatTakeoverReceipt
    extra = 0
    readonly_fields = (
        "player",
        "seat",
        "previous_owner",
        "price_paid_cents",
        "client_request_id",
        "created_at",
    )
    can_delete = False


class RaceEntryInline(admin.TabularInline):
    model = RaceEntry
    extra = 0
    readonly_fields = (
        "racer",
        "lane",
        "odds",
        "finish_place",
        "finish_tick",
        "dnf_reason",
    )
    can_delete = False


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ("round", "seed", "duration_ticks", "generated_at", "completed_at")
    readonly_fields = (
        "round",
        "seed",
        "tick_rate",
        "duration_ticks",
        "inputs",
        "timeline",
        "events",
        "result",
        "generated_at",
        "completed_at",
    )
    inlines = (RaceEntryInline,)


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("number", "state", "opened_at", "locks_at", "settled_at")
    list_filter = ("state",)
    readonly_fields = (
        "number",
        "state",
        "opened_at",
        "locks_at",
        "race_starts_at",
        "race_ends_at",
        "results_end_at",
        "settled_at",
        "created_at",
    )
    inlines = (
        RoundItemUseInline,
        RoundSeatMarketInline,
        SeatTakeoverReceiptInline,
    )


@admin.register(RoundItemUse)
class RoundItemUseAdmin(admin.ModelAdmin):
    list_display = ("player", "round", "item", "price_paid_cents", "created_at")
    readonly_fields = (
        "player",
        "round",
        "item",
        "inventory_item",
        "target_entry",
        "track_lane",
        "track_position",
        "activation_tick",
        "price_paid_cents",
        "client_request_id",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: RoundItemUse | None = None) -> bool:
        return False


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "item",
        "price_paid_cents",
        "purchased_at",
        "used_at",
        "discarded_at",
    )
    readonly_fields = (
        "player",
        "item",
        "price_paid_cents",
        "purchase_request_id",
        "purchased_at",
        "used_at",
        "discarded_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: InventoryItem | None = None) -> bool:
        return False


@admin.register(SeatOwnership)
class SeatOwnershipAdmin(admin.ModelAdmin):
    list_display = ("player", "seat", "acquired_at")
    readonly_fields = ("player", "seat", "acquired_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: SeatOwnership | None = None,
    ) -> bool:
        return False


@admin.register(SeatTakeoverReceipt)
class SeatTakeoverReceiptAdmin(admin.ModelAdmin):
    list_display = ("player", "round", "seat", "previous_owner", "price_paid_cents", "created_at")
    readonly_fields = (
        "player",
        "round",
        "seat",
        "previous_owner",
        "price_paid_cents",
        "client_request_id",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: SeatTakeoverReceipt | None = None,
    ) -> bool:
        return False
