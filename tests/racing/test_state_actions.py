from __future__ import annotations

import random

import pytest
from apps.racing.sim.engine import (
    _apply_racer_action,
    _knock_down,
    _mark_finishers,
    _move_racer,
    _RacerState,
    _start_showboat,
    simulate_race,
)
from apps.racing.sim.types import (
    ActionKind,
    RaceEffect,
    RaceEvent,
    RacerProfile,
    RacerStatus,
    SimulationConfig,
)


def profile(*, recovery: float = 0.5) -> RacerProfile:
    return RacerProfile(
        racer_id=1,
        name="State Tester",
        sprite_key="skeleton",
        color="#ffffff",
        base_speed=1.0,
        resilience=1.0,
        recovery=recovery,
        aggression=0.0,
        chaos=0.0,
    )


def racer_state(*, status: RacerStatus = RacerStatus.RUNNING) -> _RacerState:
    return _RacerState(
        profile=profile(),
        base_y=0.5,
        x=0.2,
        y=0.5,
        target_y=0.5,
        status=status,
    )


def current_status(state: _RacerState) -> RacerStatus:
    return state.status


def test_showboat_pauses_have_varied_longer_reasons_and_durations() -> None:
    config = SimulationConfig()
    durations: set[int] = set()
    messages: set[str] = set()

    for seed in range(64):
        state = racer_state()
        events: list[RaceEvent] = []
        _start_showboat(
            state=state,
            tick=100,
            rng=random.Random(seed),
            config=config,
            events=events,
        )
        durations.add(state.showboat_until - 100)
        messages.add(events[0]["message"])
        assert state.action is ActionKind.SHOWBOAT
        assert state.speed_multiplier < 0.1

    assert min(durations) >= round(1.6 * config.tick_rate)
    assert max(durations) <= round(2.8 * config.tick_rate)
    assert len(durations) >= 12
    assert len(messages) >= 10
    assert any("Mom" in message for message in messages)


def apply_action(
    state: _RacerState,
    action: ActionKind,
    *,
    tick: int,
    events: list[RaceEvent],
) -> None:
    state.action = action
    _apply_racer_action(
        action=action,
        state=state,
        tick=tick,
        lane_step=0.2,
        rng=random.Random(4),
        config=SimulationConfig(),
        events=events,
    )


def test_get_up_action_is_a_noop_while_standing() -> None:
    state = racer_state()
    events: list[RaceEvent] = []

    apply_action(state, ActionKind.GET_UP, tick=100, events=events)

    assert state.status is RacerStatus.RUNNING
    assert state.action is ActionKind.GET_UP
    assert events == []


def test_get_up_action_ends_fallen_state_only_after_minimum_crawl() -> None:
    state = racer_state(status=RacerStatus.FALLEN)
    state.state_change_available_at = 100
    state.rotation = 90
    events: list[RaceEvent] = []

    apply_action(state, ActionKind.GET_UP, tick=99, events=events)
    assert state.status is RacerStatus.FALLEN
    assert events == []

    apply_action(state, ActionKind.GET_UP, tick=100, events=events)
    assert current_status(state) is RacerStatus.RUNNING
    assert state.rotation == 0
    assert [event["kind"] for event in events] == ["recover"]


def test_turn_action_still_turns_a_crawling_racer() -> None:
    state = racer_state(status=RacerStatus.FALLEN)
    events: list[RaceEvent] = []

    apply_action(state, ActionKind.TURN, tick=40, events=events)

    assert state.status is RacerStatus.FALLEN
    assert state.target_y != state.base_y
    assert events[0]["kind"] == "lane_drift"
    assert "crawled sideways" in events[0]["message"]


def test_knocked_down_racers_always_fall_forward() -> None:
    for seed in range(20):
        state = racer_state()

        knocked_out = _knock_down(
            state=state,
            tick=20,
            impact=0.5,
            rng=random.Random(seed),
            config=SimulationConfig(knockout_scale=0),
        )

        assert knocked_out is False
        assert state.status is RacerStatus.FALLEN
        assert state.facing == 1
        assert 86 <= state.rotation <= 94


def test_knockouts_use_the_visible_knocked_out_state() -> None:
    state = racer_state()

    knocked_out = _knock_down(
        state=state,
        tick=20,
        impact=0.5,
        rng=random.Random(4),
        config=SimulationConfig(knockout_scale=100),
    )

    assert knocked_out is True
    assert state.status is RacerStatus.KNOCKED_OUT
    assert state.dnf_reason == "knocked_out"


def test_crawling_racer_can_cross_the_finish_line() -> None:
    state = racer_state(status=RacerStatus.FALLEN)
    state.x = 0.945
    state.rotation = 90
    events: list[RaceEvent] = []
    finish_order: list[int] = []
    physical_finish_order: list[int] = []
    finish_ticks: dict[int, int] = {}

    _mark_finishers(
        states=[state],
        tick=77,
        finish_order=finish_order,
        physical_finish_order=physical_finish_order,
        finish_ticks=finish_ticks,
        events=events,
        config=SimulationConfig(),
    )

    assert state.status is RacerStatus.FINISHED
    assert state.finish_tick == 77
    assert state.finish_place == 1
    assert state.rotation == 0
    assert finish_order == [1]
    assert physical_finish_order == [1]
    assert finish_ticks == {1: 77}
    assert events[0]["kind"] == "finish"
    assert events[0]["finish_place"] == 1
    assert "crawled across the line" in events[0]["message"]


def test_crawling_remains_half_speed_until_a_get_up_action() -> None:
    crawler = racer_state(status=RacerStatus.FALLEN)
    runner = racer_state()
    config = SimulationConfig()

    _move_racer(state=crawler, rng=random.Random(10), config=config)
    _move_racer(state=runner, rng=random.Random(10), config=config)

    crawl_distance = crawler.x - 0.2
    run_distance = runner.x - 0.2
    assert crawler.status is RacerStatus.FALLEN
    assert crawl_distance == pytest.approx(run_distance * 0.5)


def test_backwards_state_persists_until_turn_around_action() -> None:
    state = racer_state(status=RacerStatus.BACKWARDS)
    state.state_change_available_at = 20
    events: list[RaceEvent] = []

    for _tick in range(40):
        _move_racer(state=state, rng=random.Random(_tick), config=SimulationConfig())
    assert state.status is RacerStatus.BACKWARDS

    apply_action(state, ActionKind.TURN_AROUND, tick=40, events=events)
    assert current_status(state) is RacerStatus.RUNNING
    assert [event["kind"] for event in events] == ["turn_around"]


def test_get_up_action_is_intentionally_uncommon() -> None:
    racers = [
        profile(),
        RacerProfile(
            racer_id=2,
            name="Control",
            sprite_key="mushroom",
            color="#ffffff",
            base_speed=1.0,
            resilience=1.0,
            recovery=0.5,
            aggression=0.0,
            chaos=0.0,
        ),
    ]
    tripped = 0
    recovered = 0
    recovery_delays: list[float] = []
    for seed in range(80):
        result = simulate_race(
            racers,
            seed=seed,
            config=SimulationConfig(
                duration_seconds=15,
                knockout_scale=0,
                action_scale=0,
            ),
            effects=[RaceEffect(kind="trip_tonic", strength=0.8, racer_id=1)],
        )
        stumble_tick = next(
            (
                event["tick"]
                for event in result.events
                if event["kind"] == "stumble" and event["racer_id"] == 1
            ),
            None,
        )
        recover_tick = next(
            (
                event["tick"]
                for event in result.events
                if event["kind"] == "recover" and event["racer_id"] == 1
            ),
            None,
        )
        if stumble_tick is not None:
            tripped += 1
        if stumble_tick is not None and recover_tick is not None:
            recovered += 1
            recovery_delays.append((recover_tick - stumble_tick) / result.tick_rate)

    assert 40 <= tripped <= 65
    assert 8 <= recovered <= 25
    assert recovered < tripped / 2
    assert min(recovery_delays) >= 3.0
