from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.betting.models import BailoutPatch, BailoutSession, Bet, LedgerEntry


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "round",
        "race_entry",
        "amount_cents",
        "decimal_odds",
        "status",
        "payout_cents",
        "created_at",
    )
    list_filter = ("status", "round")
    search_fields = ("player__nickname", "race_entry__racer__name")
    readonly_fields = (
        "player",
        "round",
        "race_entry",
        "client_request_id",
        "amount_cents",
        "decimal_odds",
        "status",
        "payout_cents",
        "created_at",
        "settled_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Bet | None = None) -> bool:
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "kind",
        "amount_cents",
        "balance_after_cents",
        "round",
        "created_at",
    )
    list_filter = ("kind",)
    search_fields = ("player__nickname", "description")
    readonly_fields = (
        "player",
        "round",
        "bet",
        "kind",
        "amount_cents",
        "balance_after_cents",
        "description",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: LedgerEntry | None = None) -> bool:
        return False


@admin.register(BailoutSession)
class BailoutSessionAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "round",
        "race_entry",
        "wound_count",
        "reward_credited",
        "completed_at",
        "created_at",
    )
    list_filter = ("reward_credited", "round")
    search_fields = ("player__nickname", "race_entry__racer__name")
    readonly_fields = (
        "player",
        "round",
        "race_entry",
        "start_request_id",
        "wound_count",
        "wounds",
        "reward_credited",
        "completed_at",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: BailoutSession | None = None,
    ) -> bool:
        return False


@admin.register(BailoutPatch)
class BailoutPatchAdmin(admin.ModelAdmin):
    list_display = ("session", "wound_index", "patched_at")
    search_fields = ("session__player__nickname",)
    readonly_fields = ("session", "wound_index", "patch_request_id", "patched_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: BailoutPatch | None = None) -> bool:
        return False
