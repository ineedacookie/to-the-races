from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import replace

import pytest
from apps.racing.management.commands.seed_game import ITEMS
from apps.racing.sim.engine import (
    _TONIC_KINDS,
    _TRACK_ITEM_KINDS,
    _apply_roomba_vacuums,
    _check_obstacle_hits,
    _consume_recovery_brew,
    _destroy_in_fire_pit,
    _initialize_runtime_tonics,
    _maybe_collision,
    _maybe_trigger_potion_second_wind,
    _nitro_speed_multiplier,
    _Obstacle,
    _RacerState,
    _resolve_potion_effects,
    _revive_phoenix_states,
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


def test_seed_catalog_has_one_runtime_for_every_item_kind() -> None:
    catalog_kinds = [str(item["kind"]) for item in ITEMS]

    assert len(catalog_kinds) == len(set(catalog_kinds))
    assert set(catalog_kinds) == _TONIC_KINDS | _TRACK_ITEM_KINDS


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
        RaceEffect(
            kind="pothole",
            strength=0.85,
            effect_id=3,
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
    assert len(tick_one_potions) == 2
    assert set(result.successful_effect_ids) | set(result.failed_effect_ids) == {1, 2}


@pytest.mark.parametrize(
    ("kind", "expected_outcome"),
    [
        ("oil_slick", "backwards"),
        ("boost_pad", "boosted"),
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


@pytest.mark.parametrize(("starting_y", "expected_y"), [(0.2, 0.05), (0.8, 0.95)])
def test_boxing_glove_punches_racer_directly_into_nearest_fire_pit(
    starting_y: float,
    expected_y: float,
) -> None:
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=starting_y,
        x=0.4,
        y=starting_y,
        target_y=starting_y,
    )
    obstacle = _Obstacle(
        effect_id=99,
        kind="boxing_glove",
        x=state.x,
        y=state.y,
        strength=0.88,
        item_name="Spring-Loaded Boxing Glove",
        activation_tick=1,
        persistent=False,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(7),
        config=SimulationConfig(),
        events=events,
    )

    assert obstacle.consumed is True
    assert state.y == pytest.approx(expected_y)
    assert state.target_y == pytest.approx(expected_y)
    assert state.status == RacerStatus.DESTROYED
    assert state.dnf_reason == "fire_pit"
    assert [event["kind"] for event in events] == ["obstacle_hit", "destroyed"]
    assert "directly into the nearest fire pit" in events[0]["message"]


def test_fireproof_tonic_survives_boxing_glove_fire_pit_hit() -> None:
    config = SimulationConfig()
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=0.2,
        x=0.4,
        y=0.2,
        target_y=0.2,
        fireproof_effect_ids=[701],
    )
    obstacle = _Obstacle(
        effect_id=99,
        kind="boxing_glove",
        x=state.x,
        y=state.y,
        strength=0.88,
        item_name="Spring-Loaded Boxing Glove",
        activation_tick=1,
        persistent=False,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(7),
        config=config,
        events=events,
    )

    assert state.status == RacerStatus.RUNNING
    assert state.fireproof_effect_ids == []
    assert config.fire_pit_boundary < state.y < 1 - config.fire_pit_boundary
    assert [event["kind"] for event in events] == ["obstacle_hit", "potion_triggered"]


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


@pytest.mark.parametrize(
    ("kind", "persistent"),
    [
        ("detour_sign", True),
        ("speed_bump", True),
        ("stop_sign", False),
        ("glass_door", True),
        ("rock_wall", True),
        ("springboard", True),
        ("magnet_mine", False),
        ("portal_gate", False),
    ],
)
def test_new_track_items_have_distinct_deterministic_effects(
    kind: str,
    persistent: bool,
) -> None:
    racer_profiles = profiles()[:2]
    primary = _RacerState(
        profile=racer_profiles[0],
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    nearby = _RacerState(
        profile=racer_profiles[1],
        base_y=0.65,
        x=0.43,
        y=0.65,
        target_y=0.65,
    )
    obstacle = _Obstacle(
        effect_id=200,
        kind=kind,
        x=0.4,
        y=0.4,
        strength=0.7,
        item_name="New Item",
        activation_tick=1,
        persistent=persistent,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[primary, nearby],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(17),
        config=SimulationConfig(knockout_scale=0),
        events=events,
    )

    assert any(event["kind"] == "obstacle_hit" for event in events)
    assert obstacle.consumed is not persistent
    if kind in {"detour_sign", "rock_wall"}:
        assert primary.target_y != primary.y
    elif kind in {"speed_bump", "stop_sign"}:
        assert primary.speed_multiplier < 1
    elif kind == "glass_door":
        assert primary.speed_multiplier < 1 or primary.target_y != primary.y
    elif kind == "springboard":
        assert primary.x > 0.4
    elif kind == "magnet_mine":
        assert nearby.target_y == obstacle.y
    elif kind == "portal_gate":
        assert primary.x > 0.4


def test_detour_remains_and_slows_racers_that_do_not_change_lanes() -> None:
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    obstacle = _Obstacle(
        effect_id=301,
        kind="detour_sign",
        x=0.4,
        y=0.4,
        strength=0.55,
        item_name="Detour Sign",
        activation_tick=1,
        persistent=True,
    )

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(2),
        config=SimulationConfig(),
        events=[],
    )

    assert state.target_y == state.y
    assert state.speed_multiplier == pytest.approx(0.62)
    assert state.speed_multiplier_until == 81
    assert obstacle.consumed is False


def test_buffed_track_item_strengths_increase_their_effectiveness() -> None:
    profile = profiles()[0]
    config = SimulationConfig()

    def hit(kind: str, strength: float, *, seed: int) -> tuple[_RacerState, _Obstacle]:
        state = _RacerState(
            profile=profile,
            base_y=0.4,
            x=0.4,
            y=0.4,
            target_y=0.4,
        )
        obstacle = _Obstacle(
            effect_id=310,
            kind=kind,
            x=state.x,
            y=state.y,
            strength=strength,
            item_name="Test Item",
            activation_tick=1,
            persistent=True,
        )
        _check_obstacle_hits(
            states=[state],
            obstacles=[obstacle],
            tick=1,
            rng=random.Random(seed),
            config=config,
            events=[],
        )
        return state, obstacle

    weaker_detour, _ = hit("detour_sign", 0.55, seed=2)
    stronger_detour, _ = hit("detour_sign", 0.68, seed=2)
    assert stronger_detour.speed_multiplier < weaker_detour.speed_multiplier

    _weaker_glass, weaker_door = hit("glass_door", 0.65, seed=63)
    stronger_glass, stronger_door = hit("glass_door", 0.78, seed=63)
    assert weaker_door.consumed is True
    assert stronger_door.consumed is False
    assert stronger_glass.speed_multiplier < 1

    weaker_wall, _ = hit("rock_wall", 0.70, seed=1)
    stronger_wall, _ = hit("rock_wall", 0.82, seed=1)
    assert weaker_wall.speed_multiplier == 0
    assert stronger_wall.speed_multiplier == 0
    assert stronger_wall.speed_multiplier_until > weaker_wall.speed_multiplier_until


def test_glass_door_only_disappears_after_a_racer_breaks_through() -> None:
    profile = replace(profiles()[0], resilience=1.0)
    state = _RacerState(
        profile=profile,
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    obstacle = _Obstacle(
        effect_id=302,
        kind="glass_door",
        x=0.4,
        y=0.4,
        strength=0.65,
        item_name="Glass Door",
        activation_tick=1,
        persistent=True,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(1),
        config=SimulationConfig(),
        events=events,
    )

    assert obstacle.consumed is True
    assert state.speed_multiplier == pytest.approx(0.56)
    assert state.speed_multiplier_until == 19
    assert [event["kind"] for event in events] == [
        "obstacle_hit",
        "obstacle_removed",
    ]


def test_glass_door_failed_attempt_stops_racer_and_switches_lane() -> None:
    state = _RacerState(
        profile=profiles()[0],
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    obstacle = _Obstacle(
        effect_id=302,
        kind="glass_door",
        x=0.4,
        y=0.4,
        strength=0.78,
        item_name="Glass Door",
        activation_tick=1,
        persistent=True,
    )

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(17),
        config=SimulationConfig(),
        events=[],
    )

    assert obstacle.consumed is False
    assert state.speed_multiplier == 0
    assert state.speed_multiplier_until == 27
    assert state.target_y != state.y


def test_boost_pad_has_a_stronger_three_second_effect() -> None:
    state = _RacerState(
        profile=profiles()[0],
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    obstacle = _Obstacle(
        effect_id=303,
        kind="boost_pad",
        x=0.4,
        y=0.4,
        strength=0.6,
        item_name="Questionable Boost Pad",
        activation_tick=1,
        persistent=True,
    )

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(1),
        config=SimulationConfig(),
        events=[],
    )

    assert state.x == pytest.approx(0.538)
    assert state.speed_multiplier == pytest.approx(2.3)
    assert state.speed_multiplier_until == 61
    assert obstacle.consumed is False


def test_ghost_draught_phases_through_without_consuming_single_use_item() -> None:
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
        ghost_effect_ids=[501],
    )
    obstacle = _Obstacle(
        effect_id=502,
        kind="stop_sign",
        x=0.4,
        y=0.4,
        strength=0.7,
        item_name="Stop Sign",
        activation_tick=1,
        persistent=False,
    )
    events: list[RaceEvent] = []

    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=1,
        rng=random.Random(2),
        config=SimulationConfig(),
        events=events,
    )

    assert state.ghost_effect_ids == []
    assert state.speed_multiplier == 1
    assert obstacle.consumed is False
    assert [event["effect_id"] for event in events] == [501]


def test_roomba_slowly_vacuums_hazards_and_trips_racers_without_despawning() -> None:
    state = _RacerState(
        profile=profiles()[0],
        base_y=0.4,
        x=0.4,
        y=0.4,
        target_y=0.4,
    )
    near_hazard = _Obstacle(
        effect_id=601,
        kind="banana",
        x=0.44,
        y=0.4,
        strength=0.7,
        item_name="Banana",
        activation_tick=1,
    )
    far_hazard = _Obstacle(
        effect_id=602,
        kind="pothole",
        x=0.8,
        y=0.4,
        strength=0.7,
        item_name="Pothole",
        activation_tick=1,
    )
    roomba = _Obstacle(
        effect_id=603,
        kind="roomba_vacuum",
        x=0.4,
        y=0.4,
        strength=1.0,
        item_name="Roomba Vacuum",
        activation_tick=1,
        persistent=True,
    )
    events: list[RaceEvent] = []

    config = SimulationConfig(knockout_scale=0)
    for tick in range(1, 21):
        _apply_roomba_vacuums(
            states=[state],
            obstacles=[far_hazard, near_hazard, roomba],
            tick=tick,
            config=config,
            events=events,
        )

    assert near_hazard.consumed is True
    assert far_hazard.consumed is False
    assert 0.4 < roomba.x < near_hazard.x
    assert roomba.consumed is False
    assert [(event["kind"], event["effect_id"]) for event in events] == [("obstacle_removed", 601)]

    state.x = roomba.x
    state.y = roomba.y
    _check_obstacle_hits(
        states=[state],
        obstacles=[roomba],
        tick=21,
        rng=random.Random(3),
        config=config,
        events=events,
    )

    assert state.status == RacerStatus.FALLEN
    assert roomba.consumed is False
    assert events[-1]["kind"] == "obstacle_hit"
    assert events[-1]["effect_id"] == 603


def test_fire_pit_collision_includes_the_racers_visible_hitbox() -> None:
    state = _RacerState(
        profile=profiles()[0],
        base_y=0.8,
        x=0.4,
        y=0.89,
        target_y=0.89,
    )
    events: list[RaceEvent] = []

    _destroy_in_fire_pit(
        state=state,
        tick=10,
        config=SimulationConfig(),
        events=events,
    )

    assert state.status == RacerStatus.DESTROYED
    assert state.dnf_reason == "fire_pit"
    assert events[-1]["kind"] == "destroyed"


def test_runtime_potions_protect_recover_boost_and_revive() -> None:
    config = SimulationConfig()
    racer_profiles = profiles()[:2]
    protected = _RacerState(
        profile=racer_profiles[0],
        base_y=0.2,
        x=0.4,
        y=0.05,
        target_y=0.05,
        fireproof_effect_ids=[701],
        recovery_effects=[(702, 0.70)],
    )
    leader = _RacerState(
        profile=racer_profiles[1],
        base_y=0.6,
        x=0.6,
        y=0.6,
        target_y=0.6,
    )
    events: list[RaceEvent] = []

    _destroy_in_fire_pit(
        state=protected,
        tick=10,
        config=config,
        events=events,
    )
    assert protected.status == RacerStatus.RUNNING
    assert protected.fireproof_effect_ids == []
    assert config.fire_pit_boundary < protected.y < 1 - config.fire_pit_boundary
    _destroy_in_fire_pit(
        state=protected,
        tick=11,
        config=config,
        events=events,
    )
    assert protected.status == RacerStatus.RUNNING

    protected.state_change_available_at = 100
    _consume_recovery_brew(state=protected, tick=10, events=events)
    assert protected.state_change_available_at == 24

    protected.second_wind_effects = [(703, 0.60), (705, 0.60)]
    _maybe_trigger_potion_second_wind(
        state=protected,
        states=[protected, leader],
        tick=20,
        config=config,
        events=events,
    )
    assert protected.second_wind_effects == []
    assert protected.speed_multiplier == pytest.approx((1.0 + 0.60 * 0.4 * 2.0) ** 2)

    protected.status = RacerStatus.DESTROYED
    protected.phoenix_effect_ids = [704]
    protected.dnf_reason = "fire_pit"
    _revive_phoenix_states(
        states=[protected, leader],
        tick=30,
        config=config,
        events=events,
    )
    assert protected.status == RacerStatus.RUNNING
    assert protected.dnf_reason == ""
    assert protected.x < leader.x


def test_buffed_recovery_and_second_wind_strengths_improve_runtime_effects() -> None:
    config = SimulationConfig()
    racer_profiles = profiles()[:2]

    def state(*, recovery_strength: float, second_wind_strength: float) -> _RacerState:
        return _RacerState(
            profile=racer_profiles[0],
            base_y=0.2,
            x=0.4,
            y=0.2,
            target_y=0.2,
            state_change_available_at=100,
            recovery_effects=[(801, recovery_strength)],
            second_wind_effects=[(802, second_wind_strength)],
        )

    weaker = state(recovery_strength=0.70, second_wind_strength=0.60)
    stronger = state(recovery_strength=0.82, second_wind_strength=0.75)
    leader = _RacerState(
        profile=racer_profiles[1],
        base_y=0.6,
        x=0.6,
        y=0.6,
        target_y=0.6,
    )
    events: list[RaceEvent] = []

    _consume_recovery_brew(state=weaker, tick=10, events=events)
    _consume_recovery_brew(state=stronger, tick=10, events=events)
    assert stronger.state_change_available_at < weaker.state_change_available_at

    _maybe_trigger_potion_second_wind(
        state=weaker,
        states=[weaker, leader],
        tick=20,
        config=config,
        events=events,
    )
    _maybe_trigger_potion_second_wind(
        state=stronger,
        states=[stronger, leader],
        tick=20,
        config=config,
        events=events,
    )
    assert stronger.speed_multiplier > weaker.speed_multiplier
    assert stronger.speed_multiplier_until > weaker.speed_multiplier_until


def test_nitro_serum_stacks_compound_during_burst_and_fatigue() -> None:
    state = _RacerState(
        profile=profiles()[0],
        base_y=0.4,
        x=0.2,
        y=0.4,
        target_y=0.4,
    )
    config = SimulationConfig()
    _initialize_runtime_tonics(
        states=[state],
        effects=[
            RaceEffect(
                kind="nitro_serum",
                strength=0.6,
                effect_id=801,
                racer_id=state.profile.racer_id,
            ),
            RaceEffect(
                kind="nitro_serum",
                strength=0.6,
                effect_id=802,
                racer_id=state.profile.racer_id,
            ),
        ],
        config=config,
    )

    stack_strength = 0.6 * 0.65 * 2.0
    assert _nitro_speed_multiplier(state, 1) == pytest.approx(
        (1.0 + (0.28 + stack_strength * 0.32) * 2.0) ** 2
    )
    assert _nitro_speed_multiplier(state, state.nitro_boost_until) == pytest.approx(
        (0.82 - 0.6 * 0.08) ** 2
    )
    assert _nitro_speed_multiplier(state, state.nitro_fatigue_until) == 1


def test_no_effects_matches_legacy_signature() -> None:
    without = simulate_race(profiles(), seed=99)
    legacy = simulate_race(profiles(), seed=99, effects=None)
    assert without == legacy


def test_every_tonic_always_activates() -> None:
    kinds = [
        "speed_tonic",
        "guard_tonic",
        "trip_tonic",
        "confusion_tonic",
        "growth_tonic",
        "shrink_tonic",
        "transform_tonic",
        "fireproof_tonic",
        "nitro_serum",
        "recovery_brew",
        "ghost_draught",
        "second_wind",
        "phoenix_flask",
        "invincibility_tonic",
        "berserk_tonic",
    ]
    config = SimulationConfig(
        duration_seconds=10,
        chaos_scale=0,
        action_scale=0,
        knockout_scale=0,
    )

    for effect_id, kind in enumerate(kinds, start=1):
        for seed in range(20):
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
            assert effect_id in result.successful_effect_ids, (kind, seed)
            assert effect_id not in result.failed_effect_ids, (kind, seed)


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
    assert {"racer_id": 4, "reason": "identity_stolen"} in result.dnf
    assert all(outcome["racer_id"] != 2 for outcome in result.dnf)
    transform_event = next(
        event
        for event in result.events
        if event["kind"] == "potion_triggered" and event["racer_id"] == 4
    )
    assert transform_event["target_id"] == 2
    assert "Any finish now counts for Racer 2" in transform_event["message"]
    finish_event = next(
        event for event in result.events if event["kind"] == "finish" and event["racer_id"] == 4
    )
    assert finish_event["target_id"] == 2
    assert finish_event["finish_place"] == 1
    final_body = next(frame for frame in result.timeline[-1]["racers"] if frame["id"] == 4)
    final_identity = next(frame for frame in result.timeline[-1]["racers"] if frame["id"] == 2)
    assert final_body["state"] == "dnf"
    assert final_body["place"] is None
    assert final_identity["state"] == "finished"
    assert final_identity["place"] == 1
    assert not any(event["kind"] == "timeout" and event["racer_id"] == 2 for event in result.events)


def test_guard_tonic_does_not_cancel_hostile_tonics() -> None:
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
    for seed in range(20):
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
        assert trip.effect_id in without_guard.successful_effect_ids
        assert trip.effect_id in with_guard.successful_effect_ids
        assert trip.effect_id not in without_guard.failed_effect_ids
        assert trip.effect_id not in with_guard.failed_effect_ids


def test_same_target_stacks_all_activate_at_full_strength() -> None:
    effects = [
        RaceEffect(
            kind="speed_tonic",
            strength=0.5,
            effect_id=effect_id,
            racer_id=1,
        )
        for effect_id in (201, 202, 203)
    ]
    resolution = _resolve_potion_effects(profiles(), effects, seed=1)

    assert [effect.effect_id for effect in resolution.activated_effects] == [
        201,
        202,
        203,
    ]
    assert [effect.strength for effect in resolution.activated_effects] == [
        0.5,
        0.5,
        0.5,
    ]
    assert resolution.failed_effects == []
    expected_speed = profiles()[0].base_speed * ((1.0 + 0.5 * 2.0) ** 3)
    assert resolution.profiles[0].base_speed == pytest.approx(expected_speed)


def test_percentage_stat_tonics_compound_without_ceiling() -> None:
    effects = [
        RaceEffect(
            kind="guard_tonic",
            strength=0.5,
            effect_id=effect_id,
            racer_id=1,
        )
        for effect_id in (301, 302, 303)
    ]
    resolution = _resolve_potion_effects(profiles(), effects, seed=2)
    original = profiles()[0]

    assert resolution.profiles[0].resilience == pytest.approx(
        original.resilience * ((1.0 + 0.5 * 2.0) ** 3)
    )
    assert resolution.profiles[0].resilience > 1.0


def test_potion_adjustments_do_not_leak_into_the_next_race() -> None:
    original = profiles()
    boosted = _resolve_potion_effects(
        original,
        [RaceEffect(kind="speed_tonic", strength=0.29, effect_id=401, racer_id=1)],
        seed=3,
    )
    next_race = _resolve_potion_effects(original, [], seed=4)

    assert boosted.profiles[0].base_speed == pytest.approx(original[0].base_speed * 1.58)
    assert next_race.profiles == original


def test_invincibility_blocks_fire_and_physical_damage_without_being_consumed() -> None:
    profile = profiles()[0]
    state = _RacerState(
        profile=profile,
        base_y=0.2,
        x=0.4,
        y=0.02,
        target_y=0.02,
    )
    config = SimulationConfig(knockout_scale=100)
    events: list[RaceEvent] = []
    effect = RaceEffect(
        kind="invincibility_tonic",
        strength=1.0,
        effect_id=501,
        racer_id=profile.racer_id,
    )
    _initialize_runtime_tonics(states=[state], effects=[effect], config=config)

    _destroy_in_fire_pit(state=state, tick=1, config=config, events=events)
    assert state.status is RacerStatus.RUNNING
    assert state.invincibility_effect_ids == [501]

    obstacle = _Obstacle(
        effect_id=502,
        kind="pothole",
        x=state.x,
        y=state.y,
        strength=1.0,
        item_name="Portable Pothole",
        activation_tick=0,
    )
    _check_obstacle_hits(
        states=[state],
        obstacles=[obstacle],
        tick=2,
        rng=random.Random(1),
        config=config,
        events=events,
    )

    assert state.status is RacerStatus.RUNNING
    assert state.damage == 0
    assert state.invincibility_effect_ids == [501]
    assert sum(event["effect_id"] == 501 for event in events) == 2


def test_berserk_knocks_out_only_the_first_racer_crossed_per_stack() -> None:
    config = SimulationConfig(chaos_scale=0, action_scale=0, knockout_scale=0)
    racer_states = [
        _RacerState(
            profile=profile,
            base_y=0.4,
            x=0.4,
            y=0.4,
            target_y=0.4,
        )
        for profile in profiles()[:3]
    ]
    attacker, first_victim, second_victim = racer_states
    events: list[RaceEvent] = []
    _initialize_runtime_tonics(
        states=racer_states,
        effects=[
            RaceEffect(
                kind="berserk_tonic",
                strength=1.0,
                effect_id=601,
                racer_id=attacker.profile.racer_id,
            )
        ],
        config=config,
    )

    _maybe_collision(
        first=attacker,
        second=first_victim,
        tick=1,
        rng=random.Random(1),
        action_rng=random.Random(2),
        config=config,
        events=events,
    )
    assert first_victim.status is RacerStatus.KNOCKED_OUT
    assert attacker.berserk_effect_ids == []

    _maybe_collision(
        first=attacker,
        second=second_victim,
        tick=2,
        rng=random.Random(3),
        action_rng=random.Random(4),
        config=config,
        events=events,
    )
    assert second_victim.status is RacerStatus.RUNNING
    assert any(
        event["kind"] == "knockout"
        and event["effect_id"] == 601
        and event["racer_id"] == first_victim.profile.racer_id
        for event in events
    )


def test_invincibility_blocks_berserk_but_berserk_still_uses_its_first_crossing() -> None:
    config = SimulationConfig(chaos_scale=0, action_scale=0, knockout_scale=0)
    attacker, victim = [
        _RacerState(
            profile=profile,
            base_y=0.4,
            x=0.4,
            y=0.4,
            target_y=0.4,
        )
        for profile in profiles()[:2]
    ]
    events: list[RaceEvent] = []
    _initialize_runtime_tonics(
        states=[attacker, victim],
        effects=[
            RaceEffect(
                kind="berserk_tonic",
                strength=1.0,
                effect_id=701,
                racer_id=attacker.profile.racer_id,
            ),
            RaceEffect(
                kind="invincibility_tonic",
                strength=1.0,
                effect_id=702,
                racer_id=victim.profile.racer_id,
            ),
        ],
        config=config,
    )

    _maybe_collision(
        first=attacker,
        second=victim,
        tick=1,
        rng=random.Random(1),
        action_rng=random.Random(2),
        config=config,
        events=events,
    )

    assert victim.status is RacerStatus.RUNNING
    assert attacker.berserk_effect_ids == []
    assert victim.invincibility_effect_ids == [702]


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
