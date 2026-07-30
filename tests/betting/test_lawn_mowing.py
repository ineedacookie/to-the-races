from __future__ import annotations

import uuid

import pytest
from apps.betting.bailout_services import patch_bailout_wound, start_bailout
from apps.betting.lawn_services import (
    LAWN_CELL_COUNT,
    LAWN_REWARD_CENTS,
    LawnMowingError,
    mow_lawn_cells,
    start_lawn_mowing,
)
from apps.betting.models import LedgerEntry
from apps.players.models import Device, Player
from apps.players.services import create_player
from apps.racing.serializers import build_live_state
from tests.factories import open_round_with_entries

pytestmark = pytest.mark.django_db


def broke_player(nickname: str = "Lawn Tester") -> Player:
    player = create_player(Device.objects.create(), nickname)
    player.balance_cents = 0
    player.save(update_fields=["balance_cents", "updated_at"])
    return player


def test_mowing_persists_progress_and_pays_once() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_lawn_mowing(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    progress = mow_lawn_cells(
        player=player,
        session_id=start.session_id,
        cell_indices=[0, 1, 2],
    )
    assert progress.mowed_cells == [0, 1, 2]
    assert progress.completed is False

    completed = mow_lawn_cells(
        player=player,
        session_id=start.session_id,
        cell_indices=list(range(3, LAWN_CELL_COUNT)),
    )
    assert completed.completed is True
    assert completed.reward_cents == LAWN_REWARD_CENTS
    player.refresh_from_db()
    assert player.balance_cents == LAWN_REWARD_CENTS
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.LAWN).count() == 1

    duplicate = mow_lawn_cells(
        player=player,
        session_id=start.session_id,
        cell_indices=[0],
    )
    assert duplicate.duplicate is True
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.LAWN).count() == 1


def test_medic_and_mowing_are_independent_for_the_round() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    lawn = start_lawn_mowing(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    mow_lawn_cells(
        player=player,
        session_id=lawn.session_id,
        cell_indices=list(range(LAWN_CELL_COUNT)),
    )

    medic = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    for wound_index in range(medic.wound_count):
        patch_bailout_wound(
            player=player,
            session_id=medic.session_id,
            wound_index=wound_index,
            client_request_id=uuid.uuid4(),
        )

    player.refresh_from_db()
    assert player.balance_cents == 4_000
    state = build_live_state(player_id=player.pk)["player"]
    assert state["lawn_mowing"]["session"]["completed"] is True
    assert state["track_medic"]["session"]["completed"] is True


def test_mowing_remains_available_after_medic_pays() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player("Medic First")
    medic = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    for wound_index in range(medic.wound_count):
        patch_bailout_wound(
            player=player,
            session_id=medic.session_id,
            wound_index=wound_index,
            client_request_id=uuid.uuid4(),
        )

    player.refresh_from_db()
    assert player.balance_cents == 2_000
    lawn = start_lawn_mowing(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    assert lawn.session_id > 0


def test_mowing_is_limited_to_once_per_round() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start_lawn_mowing(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    with pytest.raises(LawnMowingError) as caught:
        start_lawn_mowing(
            player=player,
            round_id=current_round.pk,
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "lawn_unavailable"


def test_mowing_rejects_invalid_cells() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_lawn_mowing(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    with pytest.raises(LawnMowingError) as caught:
        mow_lawn_cells(
            player=player,
            session_id=start.session_id,
            cell_indices=[LAWN_CELL_COUNT],
        )
    assert caught.value.code == "invalid_cells"
