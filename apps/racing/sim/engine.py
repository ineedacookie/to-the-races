from __future__ import annotations

import random
from dataclasses import dataclass

from apps.racing.sim.types import (
    DnfResult,
    EventKind,
    RaceEffect,
    RaceEvent,
    RacerFrame,
    RacerProfile,
    RacerStatus,
    SimulationConfig,
    SimulationResult,
    TimelineFrame,
)


@dataclass(slots=True)
class _Obstacle:
    kind: str
    x: float
    y: float
    strength: float
    hit: bool = False


@dataclass(slots=True)
class _ScheduledPotion:
    kind: str
    racer_id: int
    tick: int
    strength: float


def _apply_profile_effects(
    profiles: list[RacerProfile],
    effects: list[RaceEffect],
) -> list[RacerProfile]:
    if not effects:
        return profiles

    modified: dict[int, RacerProfile] = {profile.racer_id: profile for profile in profiles}
    for effect in effects:
        if effect.racer_id is None:
            continue
        profile = modified.get(effect.racer_id)
        if profile is None:
            continue
        if effect.kind == "speed_tonic":
            modified[effect.racer_id] = RacerProfile(
                racer_id=profile.racer_id,
                name=profile.name,
                sprite_key=profile.sprite_key,
                color=profile.color,
                base_speed=min(profile.base_speed * (1.0 + effect.strength), 1.5),
                resilience=profile.resilience,
                recovery=profile.recovery,
                aggression=profile.aggression,
                chaos=profile.chaos,
            )
        elif effect.kind == "guard_tonic":
            modified[effect.racer_id] = RacerProfile(
                racer_id=profile.racer_id,
                name=profile.name,
                sprite_key=profile.sprite_key,
                color=profile.color,
                base_speed=profile.base_speed,
                resilience=min(profile.resilience + effect.strength, 1.0),
                recovery=min(profile.recovery + effect.strength * 0.5, 1.0),
                aggression=profile.aggression,
                chaos=max(profile.chaos - effect.strength * 0.5, 0.0),
            )
    return [modified[profile.racer_id] for profile in profiles]


def _build_obstacles(effects: list[RaceEffect]) -> list[_Obstacle]:
    obstacles: list[_Obstacle] = []
    for effect in effects:
        if effect.kind not in {"banana", "pothole"}:
            continue
        if effect.lane is None or effect.position is None:
            continue
        obstacles.append(
            _Obstacle(
                kind=effect.kind,
                x=effect.position,
                y=effect.lane,
                strength=effect.strength,
            )
        )
    return obstacles


def _schedule_potion_effects(
    *,
    effects: list[RaceEffect],
    seed: int,
    duration_ticks: int,
) -> list[_ScheduledPotion]:
    scheduled: list[_ScheduledPotion] = []
    potion_index = 0
    for effect in effects:
        if effect.kind not in {"trip_tonic", "confusion_tonic"} or effect.racer_id is None:
            continue
        schedule_rng = random.Random(seed ^ (effect.racer_id * 9_371) ^ (potion_index * 5_257))
        latest = max(duration_ticks // 2, 2)
        scheduled.append(
            _ScheduledPotion(
                kind=effect.kind,
                racer_id=effect.racer_id,
                tick=1 + schedule_rng.randint(0, latest - 1),
                strength=effect.strength,
            )
        )
        potion_index += 1
    return scheduled


def _potion_tick_one_events(
    *,
    effects: list[RaceEffect],
    states: list[_RacerState],
    events: list[RaceEvent],
) -> None:
    state_by_id = {state.profile.racer_id: state for state in states}
    for effect in effects:
        if effect.kind not in {
            "speed_tonic",
            "guard_tonic",
            "trip_tonic",
            "confusion_tonic",
        } or effect.racer_id is None:
            continue
        state = state_by_id.get(effect.racer_id)
        if state is None:
            continue
        label = effect.item_name or effect.kind.replace("_", " ").title()
        events.append(
            _event(
                tick=1,
                kind=EventKind.POTION_USED,
                racer=state,
                message=f"{state.profile.name} chugged {label}!",
            )
        )


def _apply_scheduled_potion(
    *,
    scheduled: _ScheduledPotion,
    state: _RacerState,
    tick: int,
    lane_step: float,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if state.status is not RacerStatus.RUNNING:
        return
    if scheduled.kind == "trip_tonic":
        state.cooldown_until = tick + round((0.7 + scheduled.strength) * config.tick_rate)
        state.status = RacerStatus.FALLEN
        state.down_until = tick + max(round((0.45 + scheduled.strength) * config.tick_rate), 2)
        state.rotation = 90.0
        state.x = max(config.start_x * 0.45, state.x - (0.006 + scheduled.strength * 0.01))
        events.append(
            _event(
                tick=tick,
                kind=EventKind.STUMBLE,
                racer=state,
                message=f"{state.profile.name} face-planted from a cursed tonic!",
            )
        )
        return

    duration = 0.55 + scheduled.strength * 0.85
    state.status = RacerStatus.BACKWARDS
    state.facing = -1
    state.backwards_until = tick + round(duration * config.tick_rate)
    state.cooldown_until = state.backwards_until + round(0.35 * config.tick_rate)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.WRONG_WAY,
            racer=state,
            message=f"{state.profile.name} sprinted toward the starting line!",
        )
    )
    state.target_y = min(max(state.base_y + lane_step * 0.35, 0.07), 0.93)


def _check_obstacle_hits(
    *,
    states: list[_RacerState],
    obstacles: list[_Obstacle],
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    for obstacle in obstacles:
        if obstacle.hit:
            continue
        for state in states:
            if state.status not in {RacerStatus.RUNNING, RacerStatus.BACKWARDS}:
                continue
            if abs(state.x - obstacle.x) > 0.022 or abs(state.y - obstacle.y) > 0.045:
                continue
            obstacle.hit = True
            impact = 0.35 + obstacle.strength * (0.85 if obstacle.kind == "pothole" else 0.45)
            label = "Portable Pothole" if obstacle.kind == "pothole" else "Banana of Binding"
            was_knocked_out = _knock_down(
                state=state,
                tick=tick,
                impact=impact,
                rng=rng,
                config=config,
            )
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.OBSTACLE_HIT,
                    racer=state,
                    message=f"{state.profile.name} hit a {label}!",
                )
            )
            if obstacle.kind == "banana":
                obstacle.y = min(obstacle.y + 0.03, 0.93)
            if was_knocked_out:
                events.append(
                    _event(
                        tick=tick,
                        kind=EventKind.KNOCKOUT,
                        racer=state,
                        message=f"{state.profile.name} was taken out by track debris!",
                    )
                )
            break


@dataclass(slots=True)
class _RacerState:
    profile: RacerProfile
    base_y: float
    x: float
    y: float
    target_y: float
    status: RacerStatus = RacerStatus.RUNNING
    facing: int = 1
    rotation: float = 0.0
    down_until: int = 0
    backwards_until: int = 0
    cooldown_until: int = 0
    damage: float = 0.0
    finish_place: int | None = None
    finish_tick: int | None = None
    dnf_reason: str = ""


def _event(
    *,
    tick: int,
    kind: EventKind,
    racer: _RacerState,
    message: str,
    target: _RacerState | None = None,
) -> RaceEvent:
    event: RaceEvent = {
        "tick": tick,
        "kind": kind.value,
        "racer_id": racer.profile.racer_id,
        "message": message,
    }
    if target is not None:
        event["target_id"] = target.profile.racer_id
    return event


def _destroy_racer(
    *,
    state: _RacerState,
    tick: int,
    reason: str,
    message: str,
    events: list[RaceEvent],
    destroyer: _RacerState | None = None,
) -> None:
    state.status = RacerStatus.DESTROYED
    state.facing = 1
    state.rotation = 180.0
    state.dnf_reason = reason
    state.cooldown_until = tick
    events.append(
        _event(
            tick=tick,
            kind=EventKind.DESTROYED,
            racer=state,
            target=destroyer,
            message=message,
        )
    )


def _destroy_in_fire_pit(
    *,
    state: _RacerState,
    tick: int,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if state.status in {
        RacerStatus.FINISHED,
        RacerStatus.KNOCKED_OUT,
        RacerStatus.DESTROYED,
        RacerStatus.DNF,
    }:
        return
    if config.fire_pit_boundary < state.y < 1.0 - config.fire_pit_boundary:
        return
    _destroy_racer(
        state=state,
        tick=tick,
        reason="fire_pit",
        message=f"{state.profile.name} wandered into a fire pit and was destroyed!",
        events=events,
    )


def _frame(tick: int, states: list[_RacerState]) -> TimelineFrame:
    racers: list[RacerFrame] = []
    for state in states:
        racers.append(
            {
                "id": state.profile.racer_id,
                "x": round(state.x, 5),
                "y": round(state.y, 5),
                "state": state.status.value,
                "facing": state.facing,
                "rotation": round(state.rotation, 2),
                "place": state.finish_place,
            }
        )
    return {"tick": tick, "racers": racers}


def _knock_down(
    *,
    state: _RacerState,
    tick: int,
    impact: float,
    rng: random.Random,
    config: SimulationConfig,
) -> bool:
    state.damage = min(
        state.damage + impact * (0.42 + ((1.0 - state.profile.resilience) * 0.58)),
        3.0,
    )
    knockout_chance = (
        0.008
        + impact * 0.055 * (1.0 - state.profile.resilience)
        + max(state.damage - 1.35, 0.0) * 0.07
    ) * config.knockout_scale
    if rng.random() < min(knockout_chance, 0.72):
        state.status = RacerStatus.DESTROYED
        state.facing = 1
        state.rotation = 90.0 if rng.random() < 0.5 else -90.0
        state.dnf_reason = "knocked_out"
        return True

    recovery_seconds = 0.55 + ((1.0 - state.profile.recovery) * 1.2) + (impact * 0.35)
    state.status = RacerStatus.FALLEN
    state.down_until = tick + max(round(recovery_seconds * config.tick_rate), 2)
    state.cooldown_until = state.down_until + round(0.45 * config.tick_rate)
    state.facing = 1
    state.rotation = 90.0 if rng.random() < 0.5 else -90.0
    state.x = max(config.start_x * 0.45, state.x - (0.008 + impact * 0.008))
    return False


def _recover_if_ready(
    state: _RacerState,
    tick: int,
    events: list[RaceEvent],
) -> None:
    if state.status is not RacerStatus.FALLEN or tick < state.down_until:
        return
    state.status = RacerStatus.RUNNING
    state.rotation = 0.0
    state.facing = 1
    state.target_y = state.base_y
    events.append(
        _event(
            tick=tick,
            kind=EventKind.RECOVER,
            racer=state,
            message=f"{state.profile.name} popped back up!",
        )
    )


def _move_racer(
    *,
    state: _RacerState,
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
) -> None:
    if state.status in {
        RacerStatus.FINISHED,
        RacerStatus.KNOCKED_OUT,
        RacerStatus.DESTROYED,
        RacerStatus.DNF,
    }:
        return

    dt = 1.0 / config.tick_rate
    y_delta = state.target_y - state.y
    state.y += y_delta * min(dt * 4.4, 1.0)
    if (
        state.status is not RacerStatus.FALLEN
        and abs(y_delta) < 0.004
        and abs(state.target_y - state.base_y) > 0.01
        and rng.random() < dt * (0.8 + state.profile.recovery)
    ):
        state.target_y = state.base_y

    speed_wobble = 0.94 + rng.random() * 0.12
    speed = config.base_track_speed * state.profile.base_speed * speed_wobble
    if state.status is RacerStatus.FALLEN:
        state.facing = 1
        state.x = min(state.x + speed * dt * 0.5, config.finish_x)
        return
    if state.status is RacerStatus.BACKWARDS and tick < state.backwards_until:
        state.facing = -1
        state.x = max(config.start_x * 0.35, state.x - speed * dt * 0.55)
        return

    if state.status is RacerStatus.BACKWARDS:
        state.status = RacerStatus.RUNNING
        state.facing = 1
    state.x += speed * dt


def _maybe_self_chaos(
    *,
    state: _RacerState,
    tick: int,
    lane_step: float,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if state.status is not RacerStatus.RUNNING or tick < state.cooldown_until:
        return
    event_rate = (0.035 + state.profile.chaos * 0.075) * config.chaos_scale
    if rng.random() >= event_rate / config.tick_rate:
        return

    roll = rng.random()
    if roll < 0.32:
        was_knocked_out = _knock_down(
            state=state,
            tick=tick,
            impact=0.35 + state.profile.chaos * 0.25,
            rng=rng,
            config=config,
        )
        if was_knocked_out:
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.KNOCKOUT,
                    racer=state,
                    message=f"{state.profile.name} tripped straight out of the race!",
                )
            )
        else:
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.STUMBLE,
                    racer=state,
                    message=f"{state.profile.name} tripped over absolutely nothing!",
                )
            )
        return

    if roll < 0.58:
        duration = 0.65 + rng.random() * (0.55 + state.profile.chaos * 0.65)
        state.status = RacerStatus.BACKWARDS
        state.facing = -1
        state.backwards_until = tick + round(duration * config.tick_rate)
        state.cooldown_until = state.backwards_until + round(0.4 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.WRONG_WAY,
                racer=state,
                message=f"{state.profile.name} forgot which way the finish line is!",
            )
        )
        return

    direction = -1 if rng.random() < 0.5 else 1
    state.target_y = min(max(state.base_y + direction * lane_step, 0.02), 0.98)
    state.cooldown_until = tick + round((0.8 + rng.random() * 0.8) * config.tick_rate)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.LANE_DRIFT,
            racer=state,
            message=f"{state.profile.name} wandered into somebody else's lane!",
        )
    )


def _maybe_stomp(
    *,
    runner: _RacerState,
    fallen: _RacerState,
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> bool:
    if runner.status not in {RacerStatus.RUNNING, RacerStatus.BACKWARDS}:
        return False
    if tick < runner.cooldown_until:
        return False
    if fallen.status is not RacerStatus.FALLEN:
        return False
    stomp_chance = (0.09 + runner.profile.aggression * 0.15) * config.chaos_scale
    if rng.random() >= stomp_chance:
        return False

    runner.cooldown_until = tick + round(0.5 * config.tick_rate)
    _destroy_racer(
        state=fallen,
        tick=tick,
        reason="stomped",
        message=f"{runner.profile.name} stomped {fallen.profile.name} into pixels!",
        events=events,
        destroyer=runner,
    )
    runner.x = min(runner.x + 0.006, config.finish_x)
    return True


def _maybe_collision(
    *,
    first: _RacerState,
    second: _RacerState,
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    active = {RacerStatus.RUNNING, RacerStatus.BACKWARDS, RacerStatus.FALLEN}
    if first.status not in active or second.status not in active:
        return
    if abs(first.x - second.x) > 0.024 or abs(first.y - second.y) > 0.042:
        return

    if _maybe_stomp(
        runner=first,
        fallen=second,
        tick=tick,
        rng=rng,
        config=config,
        events=events,
    ) or _maybe_stomp(
        runner=second,
        fallen=first,
        tick=tick,
        rng=rng,
        config=config,
        events=events,
    ):
        return

    if tick < first.cooldown_until or tick < second.cooldown_until:
        return

    if first.status is RacerStatus.FALLEN or second.status is RacerStatus.FALLEN:
        return

    collision_rate = (
        0.75 + (first.profile.aggression + second.profile.aggression) * 0.75
    ) * config.chaos_scale
    if rng.random() >= collision_rate / config.tick_rate:
        return

    total_aggression = first.profile.aggression + second.profile.aggression + 0.1
    attacker = (
        first
        if rng.random() < (first.profile.aggression + 0.05) / total_aggression
        else second
    )
    victim = second if attacker is first else first
    impact = 0.55 + attacker.profile.aggression * 0.65
    victim_knocked_out = _knock_down(
        state=victim,
        tick=tick,
        impact=impact,
        rng=rng,
        config=config,
    )
    attacker.cooldown_until = tick + round(0.55 * config.tick_rate)
    attacker.x = min(attacker.x + 0.004, config.finish_x)

    if victim_knocked_out:
        events.append(
            _event(
                tick=tick,
                kind=EventKind.KNOCKOUT,
                racer=victim,
                target=attacker,
                message=f"{attacker.profile.name} sent {victim.profile.name} to the bench!",
            )
        )
        return

    if rng.random() < 0.16 + victim.profile.chaos * 0.10:
        attacker_knocked_out = _knock_down(
            state=attacker,
            tick=tick,
            impact=impact * 0.58,
            rng=rng,
            config=config,
        )
        events.append(
            _event(
                tick=tick,
                kind=EventKind.PILEUP,
                racer=attacker,
                target=victim,
                message=f"{attacker.profile.name} and {victim.profile.name} made a pileup!",
            )
        )
        if attacker_knocked_out:
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.KNOCKOUT,
                    racer=attacker,
                    target=victim,
                    message=f"{attacker.profile.name} did not survive their own pileup!",
                )
            )
        return

    events.append(
        _event(
            tick=tick,
            kind=EventKind.BODY_CHECK,
            racer=attacker,
            target=victim,
            message=f"{attacker.profile.name} body-checked {victim.profile.name}!",
        )
    )


def _mark_finishers(
    *,
    states: list[_RacerState],
    tick: int,
    finish_order: list[int],
    events: list[RaceEvent],
    config: SimulationConfig,
) -> None:
    crossing = [
        state
        for state in states
        if state.status in {RacerStatus.RUNNING, RacerStatus.BACKWARDS}
        and state.x >= config.finish_x
    ]
    crossing.sort(key=lambda state: (-state.x, state.profile.racer_id))
    for state in crossing:
        state.x = config.finish_x
        state.status = RacerStatus.FINISHED
        state.facing = 1
        state.finish_tick = tick
        state.finish_place = len(finish_order) + 1
        finish_order.append(state.profile.racer_id)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.FINISH,
                racer=state,
                message=f"{state.profile.name} finished in place {state.finish_place}!",
            )
        )


def simulate_race(
    profiles: list[RacerProfile],
    *,
    seed: int,
    config: SimulationConfig | None = None,
    effects: list[RaceEffect] | None = None,
) -> SimulationResult:
    if len(profiles) < 2:
        raise ValueError("A race needs at least two racers.")
    if len({profile.racer_id for profile in profiles}) != len(profiles):
        raise ValueError("Racer IDs must be unique.")

    simulation = config or SimulationConfig()
    if simulation.tick_rate <= 0 or simulation.duration_seconds <= 0:
        raise ValueError("Tick rate and duration must be positive.")
    if not 0.0 < simulation.fire_pit_boundary < 0.5:
        raise ValueError("Fire pit boundary must be between zero and one half.")

    active_effects = effects or []
    adjusted_profiles = _apply_profile_effects(profiles, active_effects)
    obstacles = _build_obstacles(active_effects)
    scheduled_potions = _schedule_potion_effects(
        effects=active_effects,
        seed=seed,
        duration_ticks=simulation.duration_ticks,
    )

    rng = random.Random(seed)
    lane_step = 1.0 / (len(adjusted_profiles) + 1)
    states = [
        _RacerState(
            profile=profile,
            base_y=(index + 1) * lane_step,
            x=simulation.start_x,
            y=(index + 1) * lane_step,
            target_y=(index + 1) * lane_step,
        )
        for index, profile in enumerate(adjusted_profiles)
    ]
    events: list[RaceEvent] = []
    timeline: list[TimelineFrame] = [_frame(0, states)]
    finish_order: list[int] = []

    if active_effects:
        _potion_tick_one_events(effects=active_effects, states=states, events=events)

    state_by_id = {state.profile.racer_id: state for state in states}

    for tick in range(1, simulation.duration_ticks + 1):
        for scheduled in scheduled_potions:
            if scheduled.tick != tick:
                continue
            state = state_by_id.get(scheduled.racer_id)
            if state is None:
                continue
            _apply_scheduled_potion(
                scheduled=scheduled,
                state=state,
                tick=tick,
                lane_step=lane_step,
                config=simulation,
                events=events,
            )

        for state in states:
            _recover_if_ready(state, tick, events)
            _move_racer(state=state, tick=tick, rng=rng, config=simulation)
            _maybe_self_chaos(
                state=state,
                tick=tick,
                lane_step=lane_step,
                rng=rng,
                config=simulation,
                events=events,
            )
            _destroy_in_fire_pit(
                state=state,
                tick=tick,
                config=simulation,
                events=events,
            )

        _check_obstacle_hits(
            states=states,
            obstacles=obstacles,
            tick=tick,
            rng=rng,
            config=simulation,
            events=events,
        )

        for first_index, first in enumerate(states):
            for second in states[first_index + 1 :]:
                _maybe_collision(
                    first=first,
                    second=second,
                    tick=tick,
                    rng=rng,
                    config=simulation,
                    events=events,
                )

        _mark_finishers(
            states=states,
            tick=tick,
            finish_order=finish_order,
            events=events,
            config=simulation,
        )

        if tick % simulation.snapshot_every_ticks == 0:
            timeline.append(_frame(tick, states))
        if all(
            state.status
            in {
                RacerStatus.FINISHED,
                RacerStatus.KNOCKED_OUT,
                RacerStatus.DESTROYED,
            }
            for state in states
        ):
            if timeline[-1]["tick"] != tick:
                timeline.append(_frame(tick, states))
            break

    final_tick = timeline[-1]["tick"]
    for state in states:
        if state.status in {
            RacerStatus.FINISHED,
            RacerStatus.KNOCKED_OUT,
            RacerStatus.DESTROYED,
        }:
            continue
        final_tick = simulation.duration_ticks
        _destroy_racer(
            state=state,
            tick=final_tick,
            reason="track_consumed",
            message=f"Closing flames swallowed {state.profile.name}!",
            events=events,
        )

    if timeline[-1]["tick"] == final_tick:
        timeline[-1] = _frame(final_tick, states)
    else:
        timeline.append(_frame(final_tick, states))

    finish_ticks = {
        state.profile.racer_id: state.finish_tick
        for state in states
        if state.finish_tick is not None
    }
    dnf: list[DnfResult] = [
        {
            "racer_id": state.profile.racer_id,
            "reason": state.dnf_reason or "eliminated",
        }
        for state in states
        if state.finish_tick is None
    ]
    return SimulationResult(
        seed=seed,
        tick_rate=simulation.tick_rate,
        duration_ticks=final_tick,
        timeline=timeline,
        events=events,
        finish_order=finish_order,
        finish_ticks=finish_ticks,
        dnf=dnf,
    )
