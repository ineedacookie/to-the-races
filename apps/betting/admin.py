from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.betting.models import Bet, LedgerEntry


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
