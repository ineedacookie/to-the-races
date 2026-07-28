from __future__ import annotations

import pytest
from apps.racing.sim import engine
from apps.racing.sim.engine import _RacerState, simulate_race
from apps.racing.sim.types import RacerProfile, RacerStatus, SimulationConfig

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


def test_seeded_races_can_trigger_varied_creative_actions() -> None:
    kinds: set[str] = set()
    for seed in (0, 2, 31):
        result = simulate_race(
            action_profiles(),
            seed=seed,
            config=SimulationConfig(
                duration_seconds=60,
                action_scale=2,
                knockout_scale=0.2,
            ),
        )
        kinds.update(event["kind"] for event in result.events)

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
        seed=13,
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
        seed=31,
        config=SimulationConfig(
            duration_seconds=60,
            action_scale=2,
            knockout_scale=0.2,
        ),
    )
    racer_ids = [event["racer_id"] for event in result.events if event["kind"] == "second_wind"]

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


def test_fire_pit_resolves_before_a_creative_action_can_rescue_the_racer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rescued_racer_ids: list[int] = []

    def move_into_fire(*, state: _RacerState, **_: object) -> None:
        state.y = 0.09
        state.target_y = 0.09

    def rescue_if_still_running(*, state: _RacerState, **_: object) -> None:
        if state.status is not RacerStatus.RUNNING:
            return
        rescued_racer_ids.append(state.profile.racer_id)
        state.y = state.base_y
        state.target_y = state.base_y

    monkeypatch.setattr(engine, "_move_racer", move_into_fire)
    monkeypatch.setattr(engine, "_maybe_race_action", rescue_if_still_running)

    result = engine.simulate_race(
        action_profiles()[:2],
        seed=206,
        config=SimulationConfig(duration_seconds=1),
    )

    assert rescued_racer_ids == []
    assert result.dnf == [
        {"racer_id": 1, "reason": "fire_pit"},
        {"racer_id": 2, "reason": "fire_pit"},
    ]
    assert [event["kind"] for event in result.events].count("destroyed") == 2


def test_negative_action_scale_is_rejected() -> None:
    with pytest.raises(ValueError, match="Action scale"):
        simulate_race(
            action_profiles(),
            seed=1,
            config=SimulationConfig(action_scale=-0.1),
        )


def test_non_positive_track_speed_is_rejected() -> None:
    with pytest.raises(ValueError, match="track speed"):
        simulate_race(
            action_profiles(),
            seed=1,
            config=SimulationConfig(base_track_speed=0),
        )
