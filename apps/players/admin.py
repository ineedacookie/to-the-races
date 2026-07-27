from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.betting.services import adjust_balance
from apps.players.models import Device, Player


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("token", "player", "created_at", "last_seen_at")
    readonly_fields = ("token", "created_at", "last_seen_at")
    search_fields = ("token", "player__nickname")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("nickname", "balance_cents", "created_at", "updated_at")
    search_fields = ("nickname",)
    readonly_fields = ("created_at", "updated_at")
    actions = ("credit_100_dollars", "debit_100_dollars")

    @admin.action(description="Credit selected players $100")
    def credit_100_dollars(self, request: HttpRequest, queryset: QuerySet[Player]) -> None:
        for player in queryset:
            adjust_balance(player=player, amount_cents=10_000, description="Admin credit")
        self.message_user(request, f"Credited {queryset.count()} player(s).")

    @admin.action(description="Debit selected players $100")
    def debit_100_dollars(self, request: HttpRequest, queryset: QuerySet[Player]) -> None:
        for player in queryset:
            adjust_balance(player=player, amount_cents=-10_000, description="Admin debit")
        self.message_user(request, f"Debited {queryset.count()} player(s).")
