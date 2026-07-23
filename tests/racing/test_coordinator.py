from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from apps.betting.models import Bet
from apps.betting.services import place_bet
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import _prune_old_race_payloads, advance_once
from apps.racing.models import Race, Racer, RoomSettings, Round
from apps.racing.serializers import build_live_state
from django.utils import timezone

pytestmark = pytest.mark.django_db


def create_roster() -> None:
    for index in range(4):
        Racer.objects.create(
            name=f"Racer {index}",
            slug=f"racer-{index}",
            sprite_key=f"racer-{index}",
            color="#ffffff",
            base_speed=0.9 + index * 0.03,
            resilience=0.4 + index * 0.05,
            recovery=0.7 - index * 0.03,
            aggression=0.3 + index * 0.08,
            chaos=0.4 + index * 0.06,
            sort_order=index,
            active=True,
        )


def test_coordinator_runs_a_complete_automatic_round() -> None:
    create_roster()
    room = RoomSettings.load()
    room.betting_seconds = 5
    room.lineup_seconds = 1
    room.race_seconds = 8
    room.results_seconds = 3
    room.save()
    started_at = timezone.now()

    assert advance_once(started_at).event_names == ["round.opened"]
    current_round = Round.objects.get(number=1)
    player = create_player(Device.objects.create(), "Track Fan")
    entry = current_round.race.entries.first()
    assert entry is not None
    place_bet(
        player=player,
        race_entry_id=entry.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )

    locked = advance_once(current_round.locks_at + timedelta(milliseconds=1))
    assert locked.event_names == ["round.locked"]
    current_round.refresh_from_db()
    assert current_round.state == Round.State.LOCKED
    assert current_round.race.seed is not None
    assert current_round.race.timeline

    racing = advance_once(current_round.race_starts_at + timedelta(milliseconds=1))
    assert racing.event_names == ["race.started"]

    current_round.refresh_from_db()
    finished = advance_once(current_round.race_ends_at + timedelta(milliseconds=1))
    assert finished.event_names == ["race.finished"]
    current_round.refresh_from_db()
    assert current_round.state == Round.State.RESULTS
    assert current_round.settled_at is not None
    assert current_round.bets.get().status in {Bet.Status.WON, Bet.Status.LOST}

    next_round = advance_once(current_round.results_end_at + timedelta(milliseconds=1))
    assert next_round.event_names == ["round.opened"]
    assert Round.objects.filter(number=2, state=Round.State.OPEN).exists()


def test_live_state_only_includes_timeline_for_display() -> None:
    create_roster()
    advance_once(timezone.now())
    current_round = Round.objects.get()
    advance_once(current_round.locks_at + timedelta(milliseconds=1))

    public_state = build_live_state()
    display_state = build_live_state(include_timeline=True)

    assert "race" not in public_state["round"]
    assert display_state["round"]["race"]["timeline"]
    assert public_state["round"]["result"] == {}
    assert all(entry["finish_place"] is None for entry in public_state["round"]["entries"])

    current_round.state = Round.State.RESULTS
    current_round.save(update_fields=["state"])
    result_state = build_live_state()

    assert result_state["round"]["result"]
    assert any(entry["dnf_reason"] for entry in result_state["round"]["entries"])


def test_old_race_playback_payloads_are_pruned_without_losing_results() -> None:
    now = timezone.now()
    for number in range(1, 5):
        current_round = Round.objects.create(
            number=number,
            state=Round.State.RESULTS,
            opened_at=now,
            locks_at=now,
            race_starts_at=now,
            race_ends_at=now,
            results_end_at=now,
        )
        Race.objects.create(
            round=current_round,
            timeline=[{"tick": number}],
            events=[{"kind": "finish"}],
            result={"finish_order": [number]},
        )

    pruned = _prune_old_race_payloads(4, keep_rounds=2)

    assert pruned == 2
    assert list(
        Race.objects.filter(round__number__lte=2)
        .order_by("round__number")
        .values_list("timeline", flat=True)
    ) == [[], []]
    assert list(
        Race.objects.filter(round__number__gte=3)
        .order_by("round__number")
        .values_list("timeline", flat=True)
    ) == [[{"tick": 3}], [{"tick": 4}]]
    assert Race.objects.get(round__number=1).result == {"finish_order": [1]}
