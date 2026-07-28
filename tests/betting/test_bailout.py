from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from apps.betting.bailout_services import (
    BAILOUT_BALANCE_LIMIT_CENTS,
    BailoutError,
    patch_bailout_wound,
    start_bailout,
)
from apps.betting.bailout_wounds import (
    BAILOUT_REWARD_CENTS,
    MAX_WOUND_COUNT,
    MIN_WOUND_COUNT,
)
from apps.betting.models import BailoutPatch, BailoutSession, LedgerEntry
from apps.players.models import Device, Player
from apps.players.services import create_player
from apps.racing.models import Round
from apps.racing.serializers import build_live_state
from django.db import IntegrityError, close_old_connections
from django.test import Client
from tests.factories import open_round_with_entries

pytestmark = pytest.mark.django_db

def broke_player(
    nickname: str = "Broke Bettor",
    *,
    balance_cents: int = 0,
) -> Player:
    player = create_player(Device.objects.create(), nickname)
    player.balance_cents = balance_cents
    player.save(update_fields=["balance_cents", "updated_at"])
    return player


def test_start_bailout_assigns_two_to_five_wounds_deterministically() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()

    receipt = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    assert MIN_WOUND_COUNT <= receipt.wound_count <= MAX_WOUND_COUNT
    assert len(receipt.wounds) == receipt.wound_count
    with pytest.raises(BailoutError) as caught:
        start_bailout(
            player=player,
            round_id=current_round.pk,
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "bailout_unavailable"

    session = BailoutSession.objects.get(pk=receipt.session_id)
    replay = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=session.start_request_id,
    )
    assert replay.duplicate is True
    assert replay.session_id == receipt.session_id


def test_start_allows_balances_below_ten_dollars() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player(
        "Almost Broke",
        balance_cents=BAILOUT_BALANCE_LIMIT_CENTS - 1,
    )

    receipt = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    assert receipt.balance_cents == BAILOUT_BALANCE_LIMIT_CENTS - 1
    live_state = build_live_state(player_id=player.pk)
    assert live_state["player"]["track_medic"]["eligible"] is True


def test_start_maps_a_concurrent_session_conflict_to_a_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()

    def conflict(**_kwargs: object) -> BailoutSession:
        raise IntegrityError("duplicate player and round")

    monkeypatch.setattr(BailoutSession.objects, "create", conflict)

    with pytest.raises(BailoutError) as caught:
        start_bailout(
            player=player,
            round_id=current_round.pk,
            client_request_id=uuid.uuid4(),
        )

    assert caught.value.code == "bailout_unavailable"


def test_start_rejects_ten_dollar_balance() -> None:
    current_round, _first, _second = open_round_with_entries()
    rich = broke_player(
        "Still Loaded",
        balance_cents=BAILOUT_BALANCE_LIMIT_CENTS,
    )

    with pytest.raises(BailoutError) as rich_error:
        start_bailout(
            player=rich,
            round_id=current_round.pk,
            client_request_id=uuid.uuid4(),
        )
    assert rich_error.value.code == "balance_too_high"


@pytest.mark.parametrize(
    "round_state",
    [Round.State.LOCKED, Round.State.RACING, Round.State.RESULTS],
)
def test_start_is_available_throughout_the_current_round(round_state: str) -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player(f"Medic {round_state}")
    current_round.state = round_state
    current_round.save(update_fields=["state"])

    receipt = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    assert receipt.round_id == current_round.pk
    assert build_live_state(player_id=player.pk)["player"]["track_medic"]["eligible"] is True


def test_patch_flow_credits_twenty_dollars_once() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    for index in range(start.wound_count - 1):
        patch = patch_bailout_wound(
            player=player,
            session_id=start.session_id,
            wound_index=index,
            client_request_id=uuid.uuid4(),
        )
        assert patch.completed is False
        player.refresh_from_db()
        assert player.balance_cents == 0

    final = patch_bailout_wound(
        player=player,
        session_id=start.session_id,
        wound_index=start.wound_count - 1,
        client_request_id=uuid.uuid4(),
    )
    player.refresh_from_db()
    assert final.completed is True
    assert final.reward_cents == BAILOUT_REWARD_CENTS
    assert player.balance_cents == BAILOUT_REWARD_CENTS
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.BAILOUT).count() == 1


def test_patch_rejects_invalid_and_repeated_indices() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    with pytest.raises(BailoutError) as invalid:
        patch_bailout_wound(
            player=player,
            session_id=start.session_id,
            wound_index=start.wound_count,
            client_request_id=uuid.uuid4(),
        )
    assert invalid.value.code == "invalid_wound_index"

    request_id = uuid.uuid4()
    first_patch = patch_bailout_wound(
        player=player,
        session_id=start.session_id,
        wound_index=0,
        client_request_id=request_id,
    )
    duplicate = patch_bailout_wound(
        player=player,
        session_id=start.session_id,
        wound_index=0,
        client_request_id=request_id,
    )
    assert first_patch.duplicate is False
    assert duplicate.duplicate is True

    with pytest.raises(BailoutError) as repeated:
        patch_bailout_wound(
            player=player,
            session_id=start.session_id,
            wound_index=0,
            client_request_id=uuid.uuid4(),
        )
    assert repeated.value.code == "wound_already_patched"


def test_patch_remains_available_after_the_race_starts() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    current_round.state = Round.State.RACING
    current_round.save(update_fields=["state"])

    patch = patch_bailout_wound(
        player=player,
        session_id=start.session_id,
        wound_index=0,
        client_request_id=uuid.uuid4(),
    )

    assert patch.patched_indices == [0]


def test_patch_rejects_a_session_from_a_previous_round() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    Round.objects.create(
        number=2,
        state=Round.State.OPEN,
        opened_at=current_round.opened_at,
        locks_at=current_round.locks_at,
        race_starts_at=current_round.race_starts_at,
        race_ends_at=current_round.race_ends_at,
        results_end_at=current_round.results_end_at,
    )

    with pytest.raises(BailoutError) as stale_error:
        patch_bailout_wound(
            player=player,
            session_id=start.session_id,
            wound_index=0,
            client_request_id=uuid.uuid4(),
        )

    assert stale_error.value.code == "stale_session"
    assert not BailoutPatch.objects.filter(session_id=start.session_id).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_final_patch_credits_reward_once() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start = start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )
    for index in range(start.wound_count - 1):
        patch_bailout_wound(
            player=player,
            session_id=start.session_id,
            wound_index=index,
            client_request_id=uuid.uuid4(),
        )

    last_index = start.wound_count - 1
    barrier = Barrier(2)
    outcomes: list[str] = []

    def submit() -> None:
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            patch_bailout_wound(
                player=Player.objects.get(pk=player.pk),
                session_id=start.session_id,
                wound_index=last_index,
                client_request_id=uuid.uuid4(),
            )
            outcomes.append("ok")
        except BailoutError as error:
            outcomes.append(error.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _ignored: submit(), range(2)))

    player.refresh_from_db()
    session = BailoutSession.objects.get(pk=start.session_id)
    assert session.reward_credited is True
    assert player.balance_cents == BAILOUT_REWARD_CENTS
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.BAILOUT).count() == 1
    assert outcomes.count("ok") == 1
    assert len(outcomes) == 2
    assert outcomes.count("wound_already_patched") + outcomes.count("bailout_completed") == 1


def test_live_state_exposes_track_medic_fields() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = broke_player()
    start_bailout(
        player=player,
        round_id=current_round.pk,
        client_request_id=uuid.uuid4(),
    )

    live_state = build_live_state(player_id=player.pk)
    assert live_state["protocol_version"] == 14
    track_medic = live_state["player"]["track_medic"]
    assert track_medic["eligible"] is True
    assert track_medic["session"]["wound_count"] >= MIN_WOUND_COUNT
    assert track_medic["session"]["target"]["portrait_url"].endswith(".png")


def test_bailout_api_endpoints_are_idempotent() -> None:
    current_round, _first, _second = open_round_with_entries()
    client = Client()
    client.get("/bet/")
    client.post(
        "/api/player/",
        data='{"nickname":"Api Broke"}',
        content_type="application/json",
    )
    player = Player.objects.get(nickname="Api Broke")
    player.balance_cents = 0
    player.save(update_fields=["balance_cents", "updated_at"])

    start_request_id = str(uuid.uuid4())
    started = client.post(
        "/api/bailout/start/",
        data=(f'{{"round_id": {current_round.pk}, "client_request_id": "{start_request_id}"}}'),
        content_type="application/json",
    )
    repeated = client.post(
        "/api/bailout/start/",
        data=(f'{{"round_id": {current_round.pk}, "client_request_id": "{start_request_id}"}}'),
        content_type="application/json",
    )
    assert started.status_code == 201
    assert repeated.status_code == 200
    session_id = started.json()["bailout"]["session_id"]

    patch_request_id = str(uuid.uuid4())
    patched = client.post(
        "/api/bailout/patch/",
        data=(
            f'{{"session_id": {session_id}, "wound_index": 0, '
            f'"client_request_id": "{patch_request_id}"}}'
        ),
        content_type="application/json",
    )
    patched_again = client.post(
        "/api/bailout/patch/",
        data=(
            f'{{"session_id": {session_id}, "wound_index": 0, '
            f'"client_request_id": "{patch_request_id}"}}'
        ),
        content_type="application/json",
    )
    assert patched.status_code == 201
    assert patched_again.status_code == 200
    assert BailoutPatch.objects.filter(session_id=session_id, wound_index=0).count() == 1
