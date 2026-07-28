from __future__ import annotations

from apps.players.admin import PlayerAdmin
from apps.players.models import Player
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory


def test_player_admin_routes_balance_changes_through_ledger_actions() -> None:
    player_admin = PlayerAdmin(Player, AdminSite())
    request = RequestFactory().get("/admin/players/player/")

    assert "balance_cents" in player_admin.get_readonly_fields(request)
    assert player_admin.has_add_permission(request) is False
