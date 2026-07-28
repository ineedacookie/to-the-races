from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.racing.coordinator import _create_round
from apps.racing.models import Race, RaceEntry, Racer, RoomSettings, Round
from apps.racing.sim.profiles import (
    HISTORY_AWARE_SAMPLE_THRESHOLD,
    derive_fixed_odds,
    derive_history_aware_odds,
)
from apps.racing.sim.types import RacerProfile, SimulationConfig
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _profile(racer: Racer) -> RacerProfile:
    return RacerProfile(
        racer_id=racer.pk,
        name=racer.name,
        sprite_key=racer.sprite_key,
        color=racer.color,
        base_speed=racer.base_speed,
        resilience=racer.resilience,
        recovery=racer.recovery,
        aggression=racer.aggression,
        chaos=racer.chaos,
    )


def _settled_round_with_winner(*, number: int, winner: Racer, loser: Racer) -> None:
    now = timezone.now()
    current_round = Round.objects.create(
        number=number,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=5),
        locks_at=now - timedelta(minutes=4),
        race_starts_at=now - timedelta(minutes=3),
        race_ends_at=now - timedelta(minutes=2),
        results_end_at=now - timedelta(minutes=1),
        settled_at=now,
    )
    race = Race.objects.create(round=current_round, completed_at=now)
    RaceEntry.objects.create(
        race=race,
        racer=winner,
        lane=1,
        odds=Decimal("3.00"),
        finish_place=1,
    )
    RaceEntry.objects.create(
        race=race,
        racer=loser,
        lane=2,
        odds=Decimal("3.00"),
        finish_place=2,
    )


def test_coordinator_uses_simulation_odds_before_fifty_settled_rounds() -> None:
    room = RoomSettings.load()
    room.runner_count = 2
    room.save(update_fields=["runner_count", "updated_at"])
    winner = Racer.objects.create(name="Fast", slug="fast", sprite_key="fast", sort_order=1)
    loser = Racer.objects.create(name="Slow", slug="slow", sprite_key="slow", sort_order=2)
    for number in range(1, HISTORY_AWARE_SAMPLE_THRESHOLD):
        _settled_round_with_winner(number=number, winner=winner, loser=loser)

    current_round = _create_round(timezone.now(), room)
    entries = list(current_round.race.entries.select_related("racer").order_by("lane"))
    profiles = [_profile(entry.racer) for entry in entries]
    simulation_config = SimulationConfig(duration_seconds=room.race_seconds)
    expected = derive_fixed_odds(profiles, config=simulation_config)

    assert {entry.racer_id: entry.odds for entry in entries} == expected


def test_coordinator_switches_to_history_aware_odds_on_round_fifty_one() -> None:
    room = RoomSettings.load()
    room.runner_count = 2
    room.save(update_fields=["runner_count", "updated_at"])
    winner = Racer.objects.create(name="Fast", slug="fast", sprite_key="fast", sort_order=1)
    loser = Racer.objects.create(name="Slow", slug="slow", sprite_key="slow", sort_order=2)
    for number in range(1, HISTORY_AWARE_SAMPLE_THRESHOLD + 1):
        _settled_round_with_winner(number=number, winner=winner, loser=loser)

    current_round = _create_round(timezone.now(), room)
    entries = list(current_round.race.entries.select_related("racer").order_by("lane"))
    profiles = [_profile(entry.racer) for entry in entries]
    simulation_config = SimulationConfig(duration_seconds=room.race_seconds)
    fixed = derive_fixed_odds(profiles, config=simulation_config)
    history = derive_history_aware_odds(
        profiles,
        racer_starts={
            winner.pk: HISTORY_AWARE_SAMPLE_THRESHOLD,
            loser.pk: HISTORY_AWARE_SAMPLE_THRESHOLD,
        },
        racer_wins={winner.pk: HISTORY_AWARE_SAMPLE_THRESHOLD, loser.pk: 0},
        config=simulation_config,
    )

    actual = {entry.racer_id: entry.odds for entry in entries}
    assert actual == history
    assert actual != fixed


def test_coordinator_odds_use_each_racers_latest_fifty_results() -> None:
    room = RoomSettings.load()
    room.runner_count = 2
    room.save(update_fields=["runner_count", "updated_at"])
    early_winner = Racer.objects.create(
        name="Early Winner",
        slug="early-winner",
        sprite_key="early",
        sort_order=1,
    )
    recent_winner = Racer.objects.create(
        name="Recent Winner",
        slug="recent-winner",
        sprite_key="recent",
        sort_order=2,
    )
    for number in range(1, 11):
        _settled_round_with_winner(
            number=number,
            winner=early_winner,
            loser=recent_winner,
        )
    for number in range(11, 61):
        _settled_round_with_winner(
            number=number,
            winner=recent_winner,
            loser=early_winner,
        )

    current_round = _create_round(timezone.now(), room)
    entries = list(current_round.race.entries.select_related("racer").order_by("lane"))
    profiles = [_profile(entry.racer) for entry in entries]
    config = SimulationConfig(duration_seconds=room.race_seconds)
    recent_expected = derive_history_aware_odds(
        profiles,
        racer_starts={early_winner.pk: 50, recent_winner.pk: 50},
        racer_wins={early_winner.pk: 0, recent_winner.pk: 50},
        config=config,
    )
    lifetime_odds = derive_history_aware_odds(
        profiles,
        racer_starts={early_winner.pk: 60, recent_winner.pk: 60},
        racer_wins={early_winner.pk: 10, recent_winner.pk: 50},
        config=config,
    )

    actual = {entry.racer_id: entry.odds for entry in entries}
    assert actual == recent_expected
    assert actual != lifetime_odds


def test_history_aware_odds_respect_bounds_and_five_cent_rounding() -> None:
    profiles = [
        RacerProfile(
            racer_id=1,
            name="A",
            sprite_key="a",
            color="#fff",
            base_speed=1.5,
            resilience=1.0,
            recovery=1.0,
            aggression=0.0,
            chaos=0.0,
        ),
        RacerProfile(
            racer_id=2,
            name="B",
            sprite_key="b",
            color="#000",
            base_speed=0.5,
            resilience=0.0,
            recovery=0.0,
            aggression=1.0,
            chaos=1.0,
        ),
    ]
    odds = derive_history_aware_odds(
        profiles,
        racer_starts={1: 80, 2: 80},
        racer_wins={1: 70, 2: 10},
        trials=32,
    )

    for value in odds.values():
        assert Decimal("1.25") <= value <= Decimal("12.00")
        assert value == value.quantize(Decimal("0.05"))


def test_racers_below_fifty_starts_keep_simulation_calibrated_odds() -> None:
    profiles = [
        RacerProfile(
            racer_id=1,
            name="Hot Streak",
            sprite_key="hot",
            color="#fff",
            base_speed=1.1,
            resilience=0.5,
            recovery=0.5,
            aggression=0.5,
            chaos=0.5,
        ),
        RacerProfile(
            racer_id=2,
            name="Cold Streak",
            sprite_key="cold",
            color="#000",
            base_speed=0.9,
            resilience=0.5,
            recovery=0.5,
            aggression=0.5,
            chaos=0.5,
        ),
        RacerProfile(
            racer_id=3,
            name="Rookie",
            sprite_key="r",
            color="#999",
            base_speed=1.0,
            resilience=0.5,
            recovery=0.5,
            aggression=0.5,
            chaos=0.5,
        ),
    ]
    config = SimulationConfig(duration_seconds=60)
    fixed = derive_fixed_odds(profiles, trials=32, config=config)
    blended = derive_history_aware_odds(
        profiles,
        racer_starts={1: 60, 2: 60, 3: 5},
        racer_wins={1: 45, 2: 5, 3: 5},
        trials=32,
        config=config,
    )

    assert blended[3] == fixed[3]
    assert blended[1] != blended[2]
