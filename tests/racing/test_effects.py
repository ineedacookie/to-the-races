from __future__ import annotations

import random
from collections.abc import Callable

import pytest
from apps.racing.sim.engine import (
    _check_obstacle_hits,
    _Obstacle,
    _RacerState,
    simulate_race,
)
from apps.racing.sim.types import (
    RaceEffect,
    RaceEvent,
    RacerFrame,
    RacerProfile,
    RacerStatus,
    SimulationConfig,
)


def profiles() -> list[RacerProfile]:
    return [
        RacerProfile(
            racer_id=index,
            name=f"Racer {index}",
            sprite_key=f"racer-{index}",
            color="#ffffff",
            base_speed=0.82 + index * 0.07,
            resilience=0.25 + index * 0.08,
            recovery=0.75 - index * 0.05,
            aggression=0.20 + index * 0.11,
            chaos=0.35 + index * 0.09,
        )
        for index in range(1, 5)
    ]


def test_same_seed_and_effects_remain_deterministic() -> None:
    effects = [
        RaceEffect(kind="speed_tonic", strength=0.18, racer_id=1),
        RaceEffect(kind="trip_tonic", strength=0.45, racer_id=2),
        RaceEffect(kind="banana", strength=0.65, lane=0.4, position=0.35),
    ]
    first = simulate_race(profiles(), seed=123_456, effects=effects)
    second = simulate_race(profiles(), seed=123_456, effects=effects)

    assert first == second


def test_effects_emit_potion_and_obstacle_events() -> None:
    effects = [
        RaceEffect(kind="speed_tonic", strength=0.18, effect_id=1, racer_id=3),
        RaceEffect(kind="guard_tonic", strength=0.35, effect_id=2, racer_id=4),
        RaceEffect(kind="trip_tonic", strength=0.45, effect_id=3, racer_id=1),
        RaceEffect(kind="confusion_tonic", strength=0.40, effect_id=4, racer_id=2),
        RaceEffect(
            kind="pothole",
            strength=0.85,
            effect_id=5,
            item_name="Portable Pothole",
            lane=0.2,
            position=0.12,
        ),
    ]
    result = simulate_race(
        profiles(),
        seed=42,
        config=SimulationConfig(
            duration_seconds=12,
            chaos_scale=0,
            knockout_scale=0,
        ),
        effects=effects,
    )

    kinds = {event["kind"] for event in result.events}
    assert "potion_used" in kinds
    assert "obstacle_hit" in kinds
    assert any(
        "Portable Pothole" in event["message"]
        for event in result.events
        if event["kind"] == "obstacle_hit"
    )
    tick_one_potions = [event for event in result.events if event["kind"] == "potion_used"]
    assert all(event["tick"] == 1 for event in tick_one_potions)
    assert len(tick_one_potions) == 4
    assert set(result.successful_effect_ids) | set(result.failed_effect_ids) == {1, 2, 3, 4}


@pytest.mark.parametrize(
    ("kind", "expected_outcome"),
    [
        ("oil_slick", "backwards"),
        ("boost_pad", "boosted"),
        ("boxing_glove", "shoved"),
    ],
)
def test_each_live_item_has_a_distinct_track_effect(
    kind: str,
    expected_outcome: str,
) -> None:
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=0.2,
        x=0.4,
        y=0.2,
        target_y=0.2,
    )
    obstacle = _Obstacle(
        effect_id=99,
        kind=kind,
        x=state.x,
        y=state.y,
        strength=0.7,
        item_name="Test Item",
        activation_tick=12,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=11,
        rng=random.Random(7),
        config=SimulationConfig(),
        events=events,
    )
    assert obstacle.hit_racer_ids == set()

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=12,
        rng=random.Random(7),
        config=SimulationConfig(),
        events=events,
    )

    assert obstacle.hit_racer_ids == {profile.racer_id}
    assert len(events) == 1
    assert events[0]["kind"] == "obstacle_hit"
    assert events[0]["effect_id"] == 99
    if expected_outcome == "backwards":
        assert state.status == RacerStatus.BACKWARDS
        assert state.facing == -1
    elif expected_outcome == "boosted":
        assert state.x > 0.43
        assert state.speed_multiplier > 1
    else:
        assert state.target_y < state.y
        assert state.x < 0.4


def test_live_hazard_remains_active_until_each_racer_has_triggered_it_once() -> None:
    racer_profiles = profiles()[:2]
    states = [
        _RacerState(
            profile=profile,
            base_y=0.4,
            x=0.4,
            y=0.4,
            target_y=0.4,
        )
        for profile in racer_profiles
    ]
    obstacle = _Obstacle(
        effect_id=77,
        kind="banana",
        x=0.4,
        y=0.4,
        strength=0.65,
        item_name="Persistent Banana",
        activation_tick=1,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=states,
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(11),
        config=SimulationConfig(knockout_scale=0),
        events=events,
    )
    _check_obstacle_hits(
        states=states,
        obstacles=[obstacle],
        tick=2,
        rng=random.Random(12),
        config=SimulationConfig(knockout_scale=0),
        events=events,
    )

    assert obstacle.hit_racer_ids == {profile.racer_id for profile in racer_profiles}
    assert [event["effect_id"] for event in events] == [77, 77]


def test_no_effects_matches_legacy_signature() -> None:
    without = simulate_race(profiles(), seed=99)
    legacy = simulate_race(profiles(), seed=99, effects=None)
    assert without == legacy


def test_every_tonic_can_activate_or_fizzle() -> None:
    kinds = [
        "speed_tonic",
        "guard_tonic",
        "trip_tonic",
        "confusion_tonic",
        "growth_tonic",
        "shrink_tonic",
        "transform_tonic",
    ]
    config = SimulationConfig(
        duration_seconds=10,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )

    for effect_id, kind in enumerate(kinds, start=1):
        activations = 0
        fizzles = 0
        for seed in range(120):
            result = simulate_race(
                profiles(),
                seed=seed,
                config=config,
                effects=[
                    RaceEffect(
                        kind=kind,
                        strength=0.45,
                        effect_id=effect_id,
                        racer_id=1,
                    )
                ],
            )
            activations += effect_id in result.successful_effect_ids
            fizzles += effect_id in result.failed_effect_ids

        assert 20 <= activations <= 110, kind
        assert 10 <= fizzles <= 100, kind
        assert activations + fizzles == 120


def test_growth_shrink_and_transform_change_race_frames() -> None:
    expectations: dict[str, Callable[[RacerFrame], bool]] = {
        "growth_tonic": lambda frame: frame["scale"] > 1.0,
        "shrink_tonic": lambda frame: frame["scale"] < 1.0,
        "transform_tonic": lambda frame: frame["sprite_key"] != "racer-1",
    }
    config = SimulationConfig(
        duration_seconds=5,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )

    for effect_id, (kind, assertion) in enumerate(expectations.items(), start=20):
        successful = None
        for seed in range(100):
            candidate = simulate_race(
                profiles(),
                seed=seed,
                config=config,
                effects=[
                    RaceEffect(
                        kind=kind,
                        strength=0.5,
                        effect_id=effect_id,
                        racer_id=1,
                    )
                ],
            )
            if effect_id in candidate.successful_effect_ids:
                successful = candidate
                break

        assert successful is not None, kind
        racer_frame = successful.timeline[0]["racers"][0]
        assert assertion(racer_frame), kind


def test_identity_crisis_credits_the_borrowed_identity_for_a_physical_win() -> None:
    effect = RaceEffect(
        kind="transform_tonic",
        strength=0.5,
        effect_id=501,
        racer_id=4,
    )

    result = simulate_race(
        profiles(),
        seed=1,
        config=SimulationConfig(
            duration_seconds=120,
            chaos_scale=0,
            action_scale=0,
            knockout_scale=0,
        ),
        effects=[effect],
    )

    assert effect.effect_id in result.successful_effect_ids
    assert result.identity_racer_ids == {4: 2}
    assert result.physical_finish_order[0] == 4
    assert result.finish_order[0] == 2
    assert 4 not in result.finish_order
    assert result.finish_order.count(2) == 1
    transform_event = next(
        event
        for event in result.events
        if event["kind"] == "potion_triggered" and event["racer_id"] == 4
    )
    assert transform_event["target_id"] == 2
    assert "Any finish now counts for Racer 2" in transform_event["message"]


def test_guard_tonic_reduces_hostile_tonic_activation_rate() -> None:
    trip = RaceEffect(
        kind="trip_tonic",
        strength=0.6,
        effect_id=102,
        racer_id=1,
    )
    guard = RaceEffect(
        kind="guard_tonic",
        strength=0.5,
        effect_id=101,
        racer_id=1,
    )
    config = SimulationConfig(
        duration_seconds=10,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )
    unguarded = 0
    guarded = 0
    for seed in range(400):
        without_guard = simulate_race(
            profiles(),
            seed=seed,
            config=config,
            effects=[trip],
        )
        with_guard = simulate_race(
            profiles(),
            seed=seed,
            config=config,
            effects=[guard, trip],
        )
        unguarded += trip.effect_id in without_guard.successful_effect_ids
        guarded += trip.effect_id in with_guard.successful_effect_ids

    assert guarded < unguarded
    assert unguarded - guarded >= 35


def test_same_target_stacks_have_diminishing_activation_rates() -> None:
    effects = [
        RaceEffect(
            kind="speed_tonic",
            strength=0.5,
            effect_id=effect_id,
            racer_id=1,
        )
        for effect_id in (201, 202, 203)
    ]
    activations = {effect.effect_id: 0 for effect in effects}
    config = SimulationConfig(
        duration_seconds=3,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )

    for seed in range(400):
        result = simulate_race(profiles(), seed=seed, config=config, effects=effects)
        for effect_id in result.successful_effect_ids:
            activations[effect_id] += 1

    assert activations[201] > activations[202] > activations[203]


def test_multiple_activated_tonics_stack_their_adjustments() -> None:
    effects = [
        RaceEffect(
            kind="speed_tonic",
            strength=0.3,
            effect_id=effect_id,
            racer_id=1,
        )
        for effect_id in (601, 602)
    ]
    config = SimulationConfig(
        duration_seconds=3,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )

    single = simulate_race(
        profiles(),
        seed=5,
        config=config,
        effects=effects[:1],
    )
    stacked = simulate_race(
        profiles(),
        seed=5,
        config=config,
        effects=effects,
    )

    assert single.successful_effect_ids == [601]
    assert stacked.successful_effect_ids == [601, 602]
    single_x = single.timeline[-1]["racers"][0]["x"]
    stacked_x = stacked.timeline[-1]["racers"][0]["x"]
    assert stacked_x > single_x
