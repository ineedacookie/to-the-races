from __future__ import annotations

from apps.racing.sim.engine import simulate_race
from apps.racing.sim.types import RaceEffect, RacerProfile, SimulationConfig


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
        RaceEffect(kind="speed_tonic", strength=0.18, racer_id=3),
        RaceEffect(kind="guard_tonic", strength=0.35, racer_id=4),
        RaceEffect(kind="trip_tonic", strength=0.45, racer_id=1),
        RaceEffect(kind="confusion_tonic", strength=0.40, racer_id=2),
        RaceEffect(kind="pothole", strength=0.85, lane=0.2, position=0.3),
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
    tick_one_potions = [event for event in result.events if event["kind"] == "potion_used"]
    assert all(event["tick"] == 1 for event in tick_one_potions)
    assert len(tick_one_potions) == 4


def test_no_effects_matches_legacy_signature() -> None:
    without = simulate_race(profiles(), seed=99)
    legacy = simulate_race(profiles(), seed=99, effects=None)
    assert without == legacy
