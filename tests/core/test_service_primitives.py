from __future__ import annotations

import pytest
from apps.betting.models import LedgerEntry
from apps.betting.wallet import change_balance
from apps.core.errors import ServiceError
from apps.core.idempotency import create_idempotently
from apps.players.models import Player
from apps.racing.models import RoomSettings
from apps.racing.round_guards import betting_is_open
from django.db import transaction
from tests.factories import open_round_with_entries

pytestmark = pytest.mark.django_db


def test_wallet_change_records_the_resulting_balance() -> None:
    player = Player.objects.create(nickname="Wallet", balance_cents=1_000)

    with transaction.atomic():
        change_balance(
            player=player,
            amount_cents=-250,
            kind=LedgerEntry.Kind.ITEM,
            description="Test purchase",
        )

    entry = LedgerEntry.objects.get(player=player)
    assert player.balance_cents == 750
    assert entry.amount_cents == -250
    assert entry.balance_after_cents == 750


def test_idempotent_create_recovers_the_existing_record() -> None:
    existing = RoomSettings.load()

    recovered, duplicate = create_idempotently(
        create=lambda: RoomSettings.objects.create(pk=existing.pk),
        duplicate_queryset=lambda: RoomSettings.objects.filter(pk=existing.pk),
    )

    assert duplicate is True
    assert recovered == existing


def test_shared_betting_window_respects_room_pause() -> None:
    current_round, _first, _second = open_round_with_entries()
    room = RoomSettings.load()
    assert betting_is_open(current_round=current_round, room=room) is True

    room.is_paused = True
    assert betting_is_open(current_round=current_round, room=room) is False


def test_service_error_preserves_stable_code() -> None:
    error = ServiceError("not_allowed", "Nope.")
    assert error.code == "not_allowed"
    assert str(error) == "Nope."
