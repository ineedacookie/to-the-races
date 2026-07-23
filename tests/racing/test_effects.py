from __future__ import annotations

from collections.abc import Callable

from apps.racing.sim.engine import simulate_race
from apps.racing.sim.types import RaceEffect, RacerFrame, RacerProfile, SimulationConfig


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
