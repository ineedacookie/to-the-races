from __future__ import annotations

import pytest
from apps.racing.sim.engine import simulate_race
from apps.racing.sim.types import RacerProfile, SimulationConfig

ACTION_KINDS = {
    "showboat",
    "portal_hop",
    "second_wind",
    "evasive_juke",
    "panic_sprint",
}


def action_profiles() -> list[RacerProfile]:
    return [
        RacerProfile(
            racer_id=index,
            name=f"Action Racer {index}",
            sprite_key=f"action-racer-{index}",
            color="#ffffff",
            base_speed=1.0,
            resilience=0.45,
            recovery=0.7,
            aggression=0.65,
            chaos=0.75,
        )
        for index in range(1, 5)
    ]


def test_seeded_race_can_trigger_varied_creative_actions() -> None:
    result = simulate_race(
        action_profiles(),
        seed=7,
        config=SimulationConfig(
            duration_seconds=60,
            action_scale=2,
            knockout_scale=0.2,
        ),
    )
    kinds = {event["kind"] for event in result.events}

    assert {
        "showboat",
        "portal_hop",
        "second_wind",
        "evasive_juke",
        "panic_sprint",
    } <= kinds


def test_evasive_jukes_can_avoid_body_checks() -> None:
    result = simulate_race(
        action_profiles(),
        seed=0,
        config=SimulationConfig(
            duration_seconds=60,
            action_scale=2,
            knockout_scale=0.2,
        ),
    )
    jukes = [event for event in result.events if event["kind"] == "evasive_juke"]

    assert jukes
    assert any("target_id" in event for event in jukes)


def test_action_scale_can_disable_creative_actions() -> None:
    result = simulate_race(
        action_profiles(),
        seed=3,
        config=SimulationConfig(duration_seconds=45, action_scale=0),
    )

    assert ACTION_KINDS.isdisjoint(event["kind"] for event in result.events)


def test_second_wind_happens_at_most_once_per_racer() -> None:
    result = simulate_race(
        action_profiles(),
        seed=7,
        config=SimulationConfig(
            duration_seconds=60,
            action_scale=2,
            knockout_scale=0.2,
        ),
    )
    racer_ids = [
        event["racer_id"]
        for event in result.events
        if event["kind"] == "second_wind"
    ]

    assert racer_ids
    assert len(racer_ids) == len(set(racer_ids))


def test_action_positions_remain_inside_track_bounds() -> None:
    result = simulate_race(
        action_profiles(),
        seed=7,
        config=SimulationConfig(duration_seconds=45, knockout_scale=0.2),
    )

    assert any(event["kind"] == "portal_hop" for event in result.events)
    assert all(
        0.0 <= racer["x"] <= 0.945 and 0.0 <= racer["y"] <= 1.0
        for frame in result.timeline
        for racer in frame["racers"]
    )


def test_negative_action_scale_is_rejected() -> None:
    with pytest.raises(ValueError, match="Action scale"):
        simulate_race(
            action_profiles(),
            seed=1,
            config=SimulationConfig(action_scale=-0.1),
        )
