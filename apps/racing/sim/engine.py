from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from apps.racing.sim.types import (
    ActionKind,
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
    TrackItemFrame,
)


@dataclass(slots=True)
class _Obstacle:
    effect_id: int
    kind: str
    x: float
    y: float
    strength: float
    item_name: str
    activation_tick: int
    persistent: bool = True
    consumed: bool = False
    hit_racer_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class _ScheduledPotion:
    kind: str
    racer_id: int
    tick: int
    strength: float
    effect_id: int
    item_name: str


@dataclass(frozen=True, slots=True)
class _PotionCandidate:
    effect: RaceEffect
    effective_effect: RaceEffect
    stack_index: int
    proc_roll: float
    variant_roll: float


@dataclass(frozen=True, slots=True)
class _PotionResolution:
    profiles: list[RacerProfile]
    visual_scales: dict[int, float]
    activated_effects: list[RaceEffect]
    failed_effects: list[RaceEffect]


_TONIC_KINDS = frozenset(
    {
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
    }
)
_HOSTILE_TONIC_KINDS = frozenset({"trip_tonic", "confusion_tonic"})
_SCHEDULED_TONIC_KINDS = _HOSTILE_TONIC_KINDS
_POTION_KIND_SALTS = {
    "speed_tonic": 0x11A3,
    "guard_tonic": 0x22B5,
    "trip_tonic": 0x33C7,
    "confusion_tonic": 0x44D9,
    "growth_tonic": 0x55EB,
    "shrink_tonic": 0x66FD,
    "transform_tonic": 0x770F,
    "fireproof_tonic": 0x8811,
    "nitro_serum": 0x9923,
    "recovery_brew": 0xAA35,
    "ghost_draught": 0xBB47,
    "second_wind": 0xCC59,
    "phoenix_flask": 0xDD6B,
}
_TRACK_ITEM_KINDS = frozenset(
    {
        "banana",
        "pothole",
        "oil_slick",
        "boost_pad",
        "boxing_glove",
        "detour_sign",
        "speed_bump",
        "stop_sign",
        "glass_door",
        "rock_wall",
        "roomba_vacuum",
        "springboard",
        "magnet_mine",
        "portal_gate",
    }
)
_PERSISTENT_TRACK_ITEM_KINDS = frozenset(
    {
        "banana",
        "pothole",
        "oil_slick",
        "boost_pad",
        "detour_sign",
        "speed_bump",
        "glass_door",
        "rock_wall",
        "roomba_vacuum",
        "springboard",
    }
)
_CLEARABLE_TRACK_ITEM_KINDS = frozenset(
    {
        "banana",
        "pothole",
        "oil_slick",
        "boxing_glove",
        "detour_sign",
        "speed_bump",
        "stop_sign",
        "glass_door",
        "rock_wall",
        "magnet_mine",
    }
)
_REFERENCE_TRACK_SPEED = 0.030
_ROOMBA_TRACK_SPEED_PER_SECOND = 0.014
_ROOMBA_LANE_SPEED_PER_SECOND = 0.16
_ROOMBA_SUCTION_X = 0.028
_ROOMBA_SUCTION_Y = 0.05
_RACER_FIRE_HITBOX_RADIUS_Y = 0.022
_SHOWBOAT_DURATION_SECONDS = (1.6, 2.8)
_SHOWBOAT_SPEED_MULTIPLIER = 0.08
_SHOWBOAT_REASONS = (
    "paused to autograph a passing breeze!",
    "stopped to wave at Mom in the cheap seats!",
    "paused for an imaginary trophy ceremony!",
    "stopped to argue with their own shadow!",
    "paused to blow kisses at the fire pit!",
    "stopped to retie a shoe they are not wearing!",
    "paused for an emergency snack inspection!",
    "stopped to thank three entirely fictional sponsors!",
    "paused to check whether the finish line moved!",
    "stopped to pose for a camera that does not exist!",
    "paused to conduct the crowd like an orchestra!",
    "stopped to challenge the sun to a staring contest!",
    "paused to sign a fan's invisible sandwich!",
    "stopped because their dramatic entrance needed a sequel!",
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _pace_frequency_scale(config: SimulationConfig) -> float:
    return config.base_track_speed / _REFERENCE_TRACK_SPEED


def _potion_candidates(
    profiles: list[RacerProfile],
    effects: list[RaceEffect],
    *,
    seed: int,
) -> list[_PotionCandidate]:
    profile_ids = {profile.racer_id for profile in profiles}
    stack_counts: dict[tuple[int, str], int] = {}
    candidates: list[_PotionCandidate] = []
    for effect in effects:
        if (
            effect.kind not in _TONIC_KINDS
            or effect.racer_id is None
            or effect.racer_id not in profile_ids
        ):
            continue
        stack_key = (effect.racer_id, effect.kind)
        stack_index = stack_counts.get(stack_key, 0)
        stack_counts[stack_key] = stack_index + 1
        effective_strength = effect.strength * (0.65**stack_index)
        effect_rng = random.Random(
            seed
            ^ (effect.effect_id * 7_919)
            ^ (effect.racer_id * 9_371)
            ^ _POTION_KIND_SALTS[effect.kind]
            ^ (stack_index * 5_257)
        )
        candidates.append(
            _PotionCandidate(
                effect=effect,
                effective_effect=replace(effect, strength=effective_strength),
                stack_index=stack_index,
                proc_roll=effect_rng.random(),
                variant_roll=effect_rng.random(),
            )
        )
    return candidates


def _potion_proc_chance(
    candidate: _PotionCandidate,
    *,
    profile: RacerProfile,
    guarded: bool,
) -> float:
    chance = min(0.58 + candidate.effective_effect.strength * 0.5, 0.82)
    chance *= 0.72**candidate.stack_index
    if candidate.effect.kind in _HOSTILE_TONIC_KINDS:
        chance *= 1.0 - profile.resilience * 0.25
        if guarded:
            chance *= 0.7
    return _clamp(chance, 0.12, 0.82)


def _transform_profile(
    profile: RacerProfile,
    *,
    source: RacerProfile,
    strength: float,
) -> RacerProfile:
    blend = min(0.2 + strength * 0.5, 0.55)

    def blended(current: float, borrowed: float) -> float:
        return current * (1.0 - blend) + borrowed * blend

    return replace(
        profile,
        sprite_key=source.sprite_key,
        identity_racer_id=source.racer_id,
        base_speed=_clamp(blended(profile.base_speed, source.base_speed), 0.5, 1.5),
        resilience=_clamp(blended(profile.resilience, source.resilience), 0.0, 1.0),
        recovery=_clamp(blended(profile.recovery, source.recovery), 0.0, 1.0),
        aggression=_clamp(blended(profile.aggression, source.aggression), 0.0, 1.0),
        chaos=_clamp(blended(profile.chaos, source.chaos), 0.0, 1.0),
    )


def _resolve_potion_effects(
    profiles: list[RacerProfile],
    effects: list[RaceEffect],
    *,
    seed: int,
) -> _PotionResolution:
    candidates = _potion_candidates(profiles, effects, seed=seed)
    original = {profile.racer_id: profile for profile in profiles}
    guarded_racer_ids = {
        candidate.effect.racer_id
        for candidate in candidates
        if candidate.effect.kind == "guard_tonic"
        and candidate.effect.racer_id is not None
        and candidate.proc_roll
        < _potion_proc_chance(
            candidate,
            profile=original[candidate.effect.racer_id],
            guarded=False,
        )
    }

    activated: list[_PotionCandidate] = []
    failed: list[RaceEffect] = []
    for candidate in candidates:
        racer_id = candidate.effect.racer_id
        if racer_id is None:
            continue
        chance = _potion_proc_chance(
            candidate,
            profile=original[racer_id],
            guarded=racer_id in guarded_racer_ids,
        )
        if candidate.proc_roll < chance:
            activated.append(candidate)
        else:
            failed.append(candidate.effect)

    modified = dict(original)
    visual_scales: dict[int, float] = {}
    for candidate in activated:
        effect = candidate.effective_effect
        racer_id = effect.racer_id
        if racer_id is None:
            continue
        profile = modified[racer_id]
        if effect.kind == "speed_tonic":
            modified[racer_id] = replace(
                profile,
                base_speed=min(profile.base_speed * (1.0 + effect.strength), 1.5),
            )
        elif effect.kind == "guard_tonic":
            modified[racer_id] = replace(
                profile,
                resilience=min(profile.resilience + effect.strength, 1.0),
                recovery=min(profile.recovery + effect.strength * 0.5, 1.0),
                chaos=max(profile.chaos - effect.strength * 0.5, 0.0),
            )
        elif effect.kind == "growth_tonic":
            visual_scales[racer_id] = min(
                visual_scales.get(racer_id, 1.0) * (1.0 + effect.strength * 0.75),
                1.4,
            )
            modified[racer_id] = replace(
                profile,
                base_speed=max(profile.base_speed * (1.0 - effect.strength * 0.12), 0.5),
                resilience=min(profile.resilience + effect.strength * 0.22, 1.0),
                aggression=min(profile.aggression + effect.strength * 0.12, 1.0),
            )
        elif effect.kind == "shrink_tonic":
            visual_scales[racer_id] = max(
                visual_scales.get(racer_id, 1.0) * (1.0 - effect.strength * 0.7),
                0.65,
            )
            modified[racer_id] = replace(
                profile,
                base_speed=min(profile.base_speed * (1.0 + effect.strength * 0.1), 1.5),
                resilience=max(profile.resilience - effect.strength * 0.16, 0.0),
                recovery=min(profile.recovery + effect.strength * 0.12, 1.0),
            )
        elif effect.kind == "transform_tonic":
            possible_sources = [
                source for source in profiles if source.racer_id != profile.racer_id
            ]
            if possible_sources:
                source_index = min(
                    int(candidate.variant_roll * len(possible_sources)),
                    len(possible_sources) - 1,
                )
                modified[racer_id] = _transform_profile(
                    profile,
                    source=possible_sources[source_index],
                    strength=effect.strength,
                )

    return _PotionResolution(
        profiles=[modified[profile.racer_id] for profile in profiles],
        visual_scales=visual_scales,
        activated_effects=[candidate.effective_effect for candidate in activated],
        failed_effects=failed,
    )


def _build_obstacles(effects: list[RaceEffect]) -> list[_Obstacle]:
    obstacles: list[_Obstacle] = []
    for effect in effects:
        if effect.kind not in _TRACK_ITEM_KINDS:
            continue
        if effect.lane is None or effect.position is None:
            continue
        obstacles.append(
            _Obstacle(
                effect_id=effect.effect_id,
                kind=effect.kind,
                x=effect.position,
                y=effect.lane,
                strength=effect.strength,
                item_name=effect.item_name,
                activation_tick=effect.activation_tick,
                persistent=effect.kind in _PERSISTENT_TRACK_ITEM_KINDS,
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
        if effect.kind not in _SCHEDULED_TONIC_KINDS or effect.racer_id is None:
            continue
        schedule_rng = random.Random(
            seed ^ (effect.effect_id * 7_919) ^ (effect.racer_id * 9_371) ^ (potion_index * 5_257)
        )
        latest = max(duration_ticks // 2, 2)
        scheduled.append(
            _ScheduledPotion(
                kind=effect.kind,
                racer_id=effect.racer_id,
                tick=1 + schedule_rng.randint(0, latest - 1),
                strength=effect.strength,
                effect_id=effect.effect_id,
                item_name=effect.item_name,
            )
        )
        potion_index += 1
    return scheduled


def _potion_tick_one_events(
    *,
    effects: list[RaceEffect],
    activated_effects: list[RaceEffect],
    failed_effects: list[RaceEffect],
    states: list[_RacerState],
    events: list[RaceEvent],
) -> None:
    state_by_id = {state.profile.racer_id: state for state in states}
    activated_ids = {effect.effect_id for effect in activated_effects}
    failed_ids = {effect.effect_id for effect in failed_effects}
    for effect in effects:
        if effect.kind not in _TONIC_KINDS or effect.racer_id is None:
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
                effect_id=effect.effect_id,
            )
        )
        if effect.effect_id in failed_ids:
            events.append(
                _event(
                    tick=1,
                    kind=EventKind.POTION_FIZZLED,
                    racer=state,
                    message=f"{label} fizzled harmlessly for {state.profile.name}.",
                    effect_id=effect.effect_id,
                )
            )
        elif effect.effect_id in activated_ids and effect.kind not in _SCHEDULED_TONIC_KINDS:
            identity_state = (
                state_by_id.get(state.profile.identity_racer_id)
                if state.profile.identity_racer_id is not None
                else None
            )
            events.append(
                _event(
                    tick=1,
                    kind=EventKind.POTION_TRIGGERED,
                    racer=state,
                    target=identity_state,
                    message=_profile_potion_message(
                        effect.kind,
                        state.profile.name,
                        identity_state.profile.name if identity_state is not None else None,
                    ),
                    effect_id=effect.effect_id,
                )
            )


def _profile_potion_message(
    kind: str,
    racer_name: str,
    identity_name: str | None = None,
) -> str:
    if kind == "speed_tonic":
        return f"{racer_name}'s speed tonic kicked in!"
    if kind == "guard_tonic":
        return f"{racer_name} became suspiciously impact-resistant!"
    if kind == "growth_tonic":
        return f"{racer_name} grew to inconvenient proportions!"
    if kind == "shrink_tonic":
        return f"{racer_name} became fun-sized and hard to hit!"
    if kind == "transform_tonic" and identity_name is not None:
        return (
            f"{racer_name} stole {identity_name}'s identity! "
            f"Any finish now counts for {identity_name}."
        )
    if kind == "fireproof_tonic":
        return f"{racer_name} is fireproof for one trip through the flames!"
    if kind == "nitro_serum":
        return f"{racer_name}'s nitro burst ignited!"
    if kind == "recovery_brew":
        return f"{racer_name} banked one lightning-fast recovery!"
    if kind == "ghost_draught":
        return f"{racer_name} can phase through one obstacle or collision!"
    if kind == "second_wind":
        return f"{racer_name} armed a catch-up burst!"
    if kind == "phoenix_flask":
        return f"{racer_name} banked one fiery revival!"
    return f"{racer_name}'s potion kicked in!"


def _apply_scheduled_potion(
    *,
    scheduled: _ScheduledPotion,
    state: _RacerState,
    tick: int,
    lane_step: float,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> bool:
    if state.status is not RacerStatus.RUNNING:
        label = scheduled.item_name or scheduled.kind.replace("_", " ").title()
        events.append(
            _event(
                tick=tick,
                kind=EventKind.POTION_FIZZLED,
                racer=state,
                message=f"{label} could not find its footing on {state.profile.name}.",
                effect_id=scheduled.effect_id,
            )
        )
        return False
    events.append(
        _event(
            tick=tick,
            kind=EventKind.POTION_TRIGGERED,
            racer=state,
            message=f"{state.profile.name}'s delayed tonic suddenly activated!",
            effect_id=scheduled.effect_id,
        )
    )
    if scheduled.kind == "trip_tonic":
        state.action = ActionKind.STUMBLE
        state.cooldown_until = tick + round(0.7 * config.tick_rate)
        state.status = RacerStatus.FALLEN
        state.state_change_available_at = tick + round(
            (1.8 + scheduled.strength * 1.5) * config.tick_rate
        )
        state.rotation = 90.0
        state.target_y = state.y
        state.x = max(config.start_x * 0.45, state.x - (0.006 + scheduled.strength * 0.01))
        _consume_recovery_brew(state=state, tick=tick, events=events)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.STUMBLE,
                racer=state,
                message=f"{state.profile.name} face-planted from a cursed tonic!",
            )
        )
        return True

    state.action = ActionKind.GO_WRONG_WAY
    state.status = RacerStatus.BACKWARDS
    state.facing = -1
    state.state_change_available_at = tick + round(
        (0.8 + scheduled.strength * 0.8) * config.tick_rate
    )
    state.cooldown_until = tick + round(0.35 * config.tick_rate)
    _consume_recovery_brew(state=state, tick=tick, events=events)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.WRONG_WAY,
            racer=state,
            message=f"{state.profile.name} sprinted toward the starting line!",
        )
    )
    state.target_y = min(max(state.base_y + lane_step * 0.35, 0.07), 0.93)
    return True


def _check_obstacle_hits(
    *,
    states: list[_RacerState],
    obstacles: list[_Obstacle],
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    lane_step = 1.0 / (len(states) + 1)
    for obstacle in obstacles:
        if obstacle.consumed or tick < obstacle.activation_tick:
            continue
        for state in states:
            racer_id = state.profile.racer_id
            if racer_id in obstacle.hit_racer_ids:
                continue
            if state.status not in {RacerStatus.RUNNING, RacerStatus.BACKWARDS}:
                continue
            hitbox_scale = _clamp(state.visual_scale, 0.65, 1.4)
            if (
                abs(state.x - obstacle.x) > 0.022 * hitbox_scale
                or abs(state.y - obstacle.y) > 0.045 * hitbox_scale
            ):
                continue
            obstacle.hit_racer_ids.add(racer_id)
            label = obstacle.item_name or obstacle.kind.replace("_", " ").title()
            if _consume_ghost_draught(
                state=state,
                tick=tick,
                events=events,
                obstacle_name=label,
            ):
                break
            was_knocked_out = False
            remove_after_hit = False
            if obstacle.kind in {"banana", "pothole"}:
                impact = 0.35 + obstacle.strength * (0.85 if obstacle.kind == "pothole" else 0.45)
                was_knocked_out = _knock_down(
                    state=state,
                    tick=tick,
                    impact=impact,
                    rng=rng,
                    config=config,
                )
                if not was_knocked_out:
                    _consume_recovery_brew(state=state, tick=tick, events=events)
                outcome = "fell and started crawling"
            elif obstacle.kind == "oil_slick":
                state.status = RacerStatus.BACKWARDS
                state.facing = -1
                state.state_change_available_at = tick + round(
                    (1.2 + obstacle.strength * 0.8) * config.tick_rate
                )
                state.cooldown_until = tick + round(0.4 * config.tick_rate)
                _consume_recovery_brew(state=state, tick=tick, events=events)
                outcome = "spun around and started running backward"
            elif obstacle.kind == "boost_pad":
                state.x = min(
                    state.x + 0.045 + obstacle.strength * 0.04,
                    config.finish_x - 0.01,
                )
                _set_temporary_speed(
                    state,
                    multiplier=1.35 + obstacle.strength * 0.5,
                    until=tick + round(3.0 * config.tick_rate),
                )
                outcome = "launched forward with a powerful three-second speed boost"
            elif obstacle.kind == "boxing_glove":
                direction = -1 if state.y <= 0.5 else 1
                shove = 0.06 + obstacle.strength * 0.04
                state.target_y = _clamp(state.y + direction * shove, 0.02, 0.98)
                state.x = max(config.start_x * 0.5, state.x - 0.008)
                state.cooldown_until = tick + round(0.5 * config.tick_rate)
                outcome = "was shoved toward the nearest fire pit"
            elif obstacle.kind == "detour_sign":
                directions = [
                    direction
                    for direction in (-1, 1)
                    if 0.12 <= state.y + direction * lane_step <= 0.88
                ]
                change_lane_chance = _clamp(
                    0.55 + state.profile.recovery * 0.25,
                    0.55,
                    0.8,
                )
                if directions and rng.random() < change_lane_chance:
                    direction = rng.choice(directions)
                    state.target_y = _clamp(
                        state.y + direction * lane_step,
                        0.12,
                        0.88,
                    )
                    outcome = "obeyed the detour and changed lanes"
                else:
                    _set_temporary_speed(
                        state,
                        multiplier=0.62,
                        until=tick + round(2.0 * config.tick_rate),
                    )
                    outcome = "ignored the detour and was slowed for two seconds"
            elif obstacle.kind == "speed_bump":
                _set_temporary_speed(
                    state,
                    multiplier=max(0.5, 0.78 - obstacle.strength * 0.18),
                    until=tick + round((0.8 + obstacle.strength * 0.5) * config.tick_rate),
                )
                outcome = "slowed down without falling"
            elif obstacle.kind == "stop_sign":
                _set_temporary_speed(
                    state,
                    multiplier=0.04,
                    until=tick + round((0.55 + obstacle.strength * 0.45) * config.tick_rate),
                )
                outcome = "came to a baffling full stop"
            elif obstacle.kind == "glass_door":
                break_chance = _clamp(0.24 + state.profile.resilience * 0.62, 0.24, 0.86)
                if rng.random() < break_chance:
                    obstacle.consumed = True
                    remove_after_hit = True
                    _set_temporary_speed(
                        state,
                        multiplier=0.78,
                        until=tick + round(0.9 * config.tick_rate),
                    )
                    outcome = "broke through but lost a little speed"
                else:
                    direction = 1 if state.y < 0.5 else -1
                    state.target_y = _clamp(state.y + direction * lane_step, 0.12, 0.88)
                    _set_temporary_speed(
                        state,
                        multiplier=0.05,
                        until=tick + round(0.65 * config.tick_rate),
                    )
                    outcome = "bumped into it, paused in confusion, and switched lanes"
            elif obstacle.kind == "roomba_vacuum":
                was_knocked_out = _knock_down(
                    state=state,
                    tick=tick,
                    impact=0.42 + obstacle.strength * 0.3,
                    rng=rng,
                    config=config,
                )
                if not was_knocked_out:
                    _consume_recovery_brew(state=state, tick=tick, events=events)
                outcome = "tripped over the slow-moving vacuum"
            elif obstacle.kind == "rock_wall":
                direction = 1 if state.y < 0.5 else -1
                state.target_y = _clamp(state.y + direction * lane_step, 0.12, 0.88)
                state.cooldown_until = tick + round(0.35 * config.tick_rate)
                outcome = "had to change lanes around the wall"
            elif obstacle.kind == "springboard":
                state.x = min(
                    state.x + 0.035 + obstacle.strength * 0.045,
                    config.finish_x - 0.01,
                )
                stumble_chance = _clamp(
                    0.42 - state.profile.recovery * 0.2 - state.profile.resilience * 0.1,
                    0.12,
                    0.42,
                )
                if rng.random() < stumble_chance:
                    was_knocked_out = _knock_down(
                        state=state,
                        tick=tick,
                        impact=0.3 + obstacle.strength * 0.35,
                        rng=rng,
                        config=config,
                    )
                    if not was_knocked_out:
                        _consume_recovery_brew(state=state, tick=tick, events=events)
                    outcome = "launched forward but stumbled on the landing"
                else:
                    outcome = "launched forward and stuck the landing"
            elif obstacle.kind == "magnet_mine":
                pull_range = 0.11 + obstacle.strength * 0.06
                for nearby in states:
                    if (
                        nearby.status
                        in {
                            RacerStatus.RUNNING,
                            RacerStatus.BACKWARDS,
                            RacerStatus.FALLEN,
                        }
                        and abs(nearby.x - obstacle.x) <= pull_range
                    ):
                        nearby.target_y = _clamp(obstacle.y, 0.12, 0.88)
                        nearby.cooldown_until = max(
                            nearby.cooldown_until,
                            tick + round(0.25 * config.tick_rate),
                        )
                outcome = "pulled nearby racers into one collision-prone lane"
            elif obstacle.kind == "portal_gate":
                maximum_jump = max(config.finish_x - state.x - 0.03, 0.0)
                requested_jump = rng.uniform(0.06, 0.13 + obstacle.strength * 0.08)
                state.x += min(requested_jump, maximum_jump)
                safe_lanes = [(index + 1) * lane_step for index in range(len(states))]
                destination_y = rng.choice(safe_lanes)
                state.y = destination_y
                state.target_y = destination_y
                outcome = "teleported to a random later track position"
                events.append(
                    _event(
                        tick=tick,
                        kind=EventKind.PORTAL_HOP,
                        racer=state,
                        message=f"{state.profile.name} vanished through {label}!",
                        effect_id=obstacle.effect_id,
                    )
                )
            else:
                raise ValueError(f"Unsupported obstacle kind: {obstacle.kind}")
            if not obstacle.persistent:
                obstacle.consumed = True
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.OBSTACLE_HIT,
                    racer=state,
                    message=f"{state.profile.name} hit {label} and {outcome}!",
                    effect_id=obstacle.effect_id,
                )
            )
            if remove_after_hit:
                events.append(
                    _event(
                        tick=tick,
                        kind=EventKind.OBSTACLE_REMOVED,
                        racer=state,
                        message=f"{label} shattered and was cleared from the track!",
                        effect_id=obstacle.effect_id,
                    )
                )
            if was_knocked_out:
                events.append(
                    _event(
                        tick=tick,
                        kind=EventKind.KNOCKOUT,
                        racer=state,
                        message=f"{state.profile.name} was taken out by track debris!",
                        effect_id=obstacle.effect_id,
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
    action: ActionKind | None = None
    state_change_available_at: int = 0
    cooldown_until: int = 0
    action_cooldown_until: int = 0
    speed_multiplier: float = 1.0
    speed_multiplier_until: int = 0
    showboat_until: int = 0
    second_wind_used: bool = False
    visual_scale: float = 1.0
    damage: float = 0.0
    finish_place: int | None = None
    finish_tick: int | None = None
    dnf_reason: str = ""
    fireproof_effect_ids: list[int] = field(default_factory=list)
    recovery_effect_ids: list[int] = field(default_factory=list)
    ghost_effect_ids: list[int] = field(default_factory=list)
    second_wind_effect_ids: list[int] = field(default_factory=list)
    phoenix_effect_ids: list[int] = field(default_factory=list)
    nitro_effect_id: int | None = None
    nitro_strength: float = 0.0
    nitro_boost_until: int = 0
    nitro_fatigue_until: int = 0


def _event(
    *,
    tick: int,
    kind: EventKind,
    racer: _RacerState,
    message: str,
    target: _RacerState | None = None,
    effect_id: int | None = None,
    finish_place: int | None = None,
) -> RaceEvent:
    event: RaceEvent = {
        "tick": tick,
        "kind": kind.value,
        "racer_id": racer.profile.racer_id,
        "message": message,
    }
    if target is not None:
        event["target_id"] = target.profile.racer_id
    if effect_id is not None:
        event["effect_id"] = effect_id
    if finish_place is not None or kind is EventKind.FINISH:
        event["finish_place"] = finish_place
    return event


def _initialize_runtime_tonics(
    *,
    states: list[_RacerState],
    effects: list[RaceEffect],
    config: SimulationConfig,
) -> None:
    state_by_id = {state.profile.racer_id: state for state in states}
    for effect in effects:
        if effect.racer_id is None:
            continue
        state = state_by_id.get(effect.racer_id)
        if state is None:
            continue
        if effect.kind == "fireproof_tonic":
            state.fireproof_effect_ids.append(effect.effect_id)
        elif effect.kind == "recovery_brew":
            state.recovery_effect_ids.append(effect.effect_id)
        elif effect.kind == "ghost_draught":
            state.ghost_effect_ids.append(effect.effect_id)
        elif effect.kind == "second_wind":
            state.second_wind_effect_ids.append(effect.effect_id)
        elif effect.kind == "phoenix_flask":
            state.phoenix_effect_ids.append(effect.effect_id)
        elif effect.kind == "nitro_serum":
            state.nitro_effect_id = effect.effect_id
            state.nitro_strength = _clamp(
                state.nitro_strength + effect.strength * 0.65,
                0.0,
                1.0,
            )
            boost_ticks = max(
                round((1.4 + state.nitro_strength * 1.1) * config.tick_rate),
                1,
            )
            fatigue_ticks = max(
                round((1.0 + state.nitro_strength * 1.2) * config.tick_rate),
                1,
            )
            state.nitro_boost_until = max(state.nitro_boost_until, 1 + boost_ticks)
            state.nitro_fatigue_until = max(
                state.nitro_fatigue_until,
                state.nitro_boost_until + fatigue_ticks,
            )


def _nitro_speed_multiplier(state: _RacerState, tick: int) -> float:
    if tick < state.nitro_boost_until:
        return 1.28 + state.nitro_strength * 0.32
    if tick < state.nitro_fatigue_until:
        return max(0.82 - state.nitro_strength * 0.08, 0.7)
    return 1.0


def _consume_recovery_brew(
    *,
    state: _RacerState,
    tick: int,
    events: list[RaceEvent],
) -> None:
    if not state.recovery_effect_ids:
        return
    effect_id = state.recovery_effect_ids.pop(0)
    remaining_ticks = max(state.state_change_available_at - tick, 0)
    state.state_change_available_at = tick + max(round(remaining_ticks * 0.3), 1)
    state.cooldown_until = min(state.cooldown_until, tick + 2)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.RECOVER,
            racer=state,
            message=f"{state.profile.name}'s Recovery Brew accelerated the recovery!",
            effect_id=effect_id,
        )
    )


def _consume_ghost_draught(
    *,
    state: _RacerState,
    tick: int,
    events: list[RaceEvent],
    obstacle_name: str | None = None,
) -> bool:
    if not state.ghost_effect_ids:
        return False
    effect_id = state.ghost_effect_ids.pop(0)
    subject = obstacle_name or "a collision"
    events.append(
        _event(
            tick=tick,
            kind=EventKind.POTION_TRIGGERED,
            racer=state,
            message=f"{state.profile.name} ghosted harmlessly through {subject}!",
            effect_id=effect_id,
        )
    )
    return True


def _maybe_trigger_potion_second_wind(
    *,
    state: _RacerState,
    states: list[_RacerState],
    tick: int,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if (
        not state.second_wind_effect_ids
        or state.status is not RacerStatus.RUNNING
        or state.x < config.start_x + 0.03
    ):
        return
    active = [
        candidate.x
        for candidate in states
        if candidate is not state
        and candidate.status
        in {
            RacerStatus.RUNNING,
            RacerStatus.BACKWARDS,
            RacerStatus.FALLEN,
        }
    ]
    if not active or max(active) - state.x < 0.075:
        return
    effect_id = state.second_wind_effect_ids.pop(0)
    state.second_wind_used = True
    _set_temporary_speed(
        state,
        multiplier=1.24,
        until=tick + round(2.8 * config.tick_rate),
    )
    events.append(
        _event(
            tick=tick,
            kind=EventKind.SECOND_WIND,
            racer=state,
            message=f"{state.profile.name}'s bottled second wind kicked in from behind!",
            effect_id=effect_id,
        )
    )


def _revive_phoenix_states(
    *,
    states: list[_RacerState],
    tick: int,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    terminal = {RacerStatus.KNOCKED_OUT, RacerStatus.DESTROYED}
    for state in states:
        if state.status not in terminal or not state.phoenix_effect_ids:
            continue
        effect_id = state.phoenix_effect_ids.pop(0)
        active_positions = [
            candidate.x
            for candidate in states
            if candidate is not state
            and candidate.status
            in {
                RacerStatus.RUNNING,
                RacerStatus.BACKWARDS,
                RacerStatus.FALLEN,
            }
        ]
        state.x = (
            max(config.start_x + 0.02, min(active_positions) - 0.04)
            if active_positions
            else config.start_x + 0.02
        )
        state.y = state.base_y
        state.target_y = state.base_y
        state.status = RacerStatus.RUNNING
        state.facing = 1
        state.rotation = 0.0
        state.damage = min(state.damage, 0.55)
        state.dnf_reason = ""
        state.cooldown_until = tick + round(0.6 * config.tick_rate)
        state.state_change_available_at = tick
        events.append(
            _event(
                tick=tick,
                kind=EventKind.RECOVER,
                racer=state,
                message=f"{state.profile.name} erupted from the Phoenix Flask back into the race!",
                effect_id=effect_id,
            )
        )


def _apply_roomba_vacuums(
    *,
    states: list[_RacerState],
    obstacles: list[_Obstacle],
    tick: int,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    for roomba in obstacles:
        if (
            roomba.kind != "roomba_vacuum"
            or roomba.consumed
            or tick < roomba.activation_tick
        ):
            continue
        candidates = [
            obstacle
            for obstacle in obstacles
            if obstacle is not roomba
            and obstacle.kind in _CLEARABLE_TRACK_ITEM_KINDS
            and not obstacle.consumed
            and tick >= obstacle.activation_tick
        ]
        if not candidates:
            roomba.x = min(
                roomba.x + (_ROOMBA_TRACK_SPEED_PER_SECOND * 0.45 / config.tick_rate),
                config.finish_x,
            )
            if roomba.x < config.finish_x:
                continue
            roomba.consumed = True
            anchor = min(
                states,
                key=lambda state: abs(state.x - roomba.x) + abs(state.y - roomba.y),
            )
            events.append(
                _event(
                    tick=tick,
                    kind=EventKind.ITEM_CLEARED,
                    racer=anchor,
                    message="The Roomba Vacuum finished its patrol and rolled away.",
                    effect_id=roomba.effect_id,
                )
            )
            continue
        target = min(
            candidates,
            key=lambda obstacle: abs(obstacle.x - roomba.x) + abs(obstacle.y - roomba.y),
        )
        x_step = _ROOMBA_TRACK_SPEED_PER_SECOND / config.tick_rate
        y_step = _ROOMBA_LANE_SPEED_PER_SECOND / config.tick_rate
        roomba.x = _clamp(
            roomba.x + _clamp(target.x - roomba.x, -x_step, x_step),
            config.start_x,
            config.finish_x,
        )
        roomba.y = _clamp(
            roomba.y + _clamp(target.y - roomba.y, -y_step, y_step),
            0.07,
            0.93,
        )
        if (
            abs(target.x - roomba.x) > _ROOMBA_SUCTION_X
            or abs(target.y - roomba.y) > _ROOMBA_SUCTION_Y
        ):
            continue
        target.consumed = True
        anchor = min(
            states,
            key=lambda state: abs(state.x - roomba.x) + abs(state.y - roomba.y),
        )
        target_label = target.item_name or target.kind.replace("_", " ").title()
        events.append(
            _event(
                tick=tick,
                kind=EventKind.OBSTACLE_REMOVED,
                racer=anchor,
                message=f"The Roomba Vacuum sucked up {target_label}!",
                effect_id=target.effect_id,
            )
        )


def _destroy_racer(
    *,
    state: _RacerState,
    tick: int,
    finish_x: float,
    reason: str,
    message: str,
    events: list[RaceEvent],
    destroyer: _RacerState | None = None,
) -> None:
    state.x = _clamp(state.x, 0.0, finish_x)
    state.y = _clamp(state.y, 0.0, 1.0)
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
    hitbox_radius = min(
        _RACER_FIRE_HITBOX_RADIUS_Y * _clamp(state.visual_scale, 0.65, 1.4),
        max(0.5 - config.fire_pit_boundary - 0.001, 0.0),
    )
    safe_top = config.fire_pit_boundary + hitbox_radius
    safe_bottom = 1.0 - config.fire_pit_boundary - hitbox_radius
    if safe_top < state.y < safe_bottom:
        return
    if state.fireproof_effect_ids:
        effect_id = state.fireproof_effect_ids.pop(0)
        midpoint = (safe_top + safe_bottom) / 2
        safe_y = (
            min(safe_top + 0.015, midpoint)
            if state.y <= midpoint
            else max(safe_bottom - 0.015, midpoint)
        )
        state.y = safe_y
        state.target_y = safe_y
        events.append(
            _event(
                tick=tick,
                kind=EventKind.POTION_TRIGGERED,
                racer=state,
                message=f"{state.profile.name} walked through the fire pit completely unharmed!",
                effect_id=effect_id,
            )
        )
        return
    _destroy_racer(
        state=state,
        tick=tick,
        finish_x=config.finish_x,
        reason="fire_pit",
        message=f"{state.profile.name} wandered into a fire pit and was destroyed!",
        events=events,
    )


def _frame(
    tick: int,
    states: list[_RacerState],
    obstacles: list[_Obstacle],
) -> TimelineFrame:
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
                "scale": round(state.visual_scale, 3),
                "sprite_key": state.profile.sprite_key,
                "place": state.finish_place,
            }
        )
    track_items: list[TrackItemFrame] = [
        {
            "id": obstacle.effect_id,
            "x": round(obstacle.x, 5),
            "y": round(obstacle.y, 5),
            "active": not obstacle.consumed,
        }
        for obstacle in obstacles
        if obstacle.kind == "roomba_vacuum" and tick >= obstacle.activation_tick
    ]
    return {"tick": tick, "racers": racers, "track_items": track_items}


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
        state.x = _clamp(state.x, 0.0, config.finish_x)
        state.y = _clamp(state.y, 0.0, 1.0)
        state.status = RacerStatus.KNOCKED_OUT
        state.facing = 1
        state.rotation = 90.0 if rng.random() < 0.5 else -90.0
        state.dnf_reason = "knocked_out"
        return True

    minimum_crawl_seconds = 1.75 + ((1.0 - state.profile.recovery) * 1.25) + (impact * 0.65)
    state.status = RacerStatus.FALLEN
    state.state_change_available_at = tick + max(
        round(minimum_crawl_seconds * config.tick_rate),
        2,
    )
    state.cooldown_until = tick + round(0.45 * config.tick_rate)
    state.facing = 1
    state.rotation = 86.0 + rng.random() * 8.0
    state.target_y = state.y
    state.x = max(config.start_x * 0.45, state.x - (0.008 + impact * 0.008))
    return False


def _choose_racer_action(
    *,
    state: _RacerState,
    rng: random.Random,
    config: SimulationConfig,
) -> ActionKind | None:
    if state.status in {
        RacerStatus.FINISHED,
        RacerStatus.KNOCKED_OUT,
        RacerStatus.DESTROYED,
        RacerStatus.DNF,
    }:
        return None

    chaos_scale = min(max(config.chaos_scale, 0.0), 3.0)
    action_rates = (
        (ActionKind.GET_UP, 0.025 + state.profile.recovery * 0.035),
        (ActionKind.TURN, (0.018 + state.profile.chaos * 0.032) * chaos_scale),
        (ActionKind.STUMBLE, (0.008 + state.profile.chaos * 0.022) * chaos_scale),
        (
            ActionKind.GO_WRONG_WAY,
            (0.006 + state.profile.chaos * 0.016) * chaos_scale,
        ),
        (ActionKind.TURN_AROUND, 0.045 + state.profile.recovery * 0.055),
    )
    roll = rng.random()
    cumulative_chance = 0.0
    frequency_scale = _pace_frequency_scale(config)
    for action, rate_per_second in action_rates:
        cumulative_chance += rate_per_second * frequency_scale / config.tick_rate
        if roll < cumulative_chance:
            return action
    return None


def _turn_destination(
    *,
    state: _RacerState,
    lane_step: float,
    rng: random.Random,
) -> float:
    candidates = [
        state.base_y,
        min(max(state.base_y - lane_step, 0.02), 0.98),
        min(max(state.base_y + lane_step, 0.02), 0.98),
    ]
    distinct = [candidate for candidate in candidates if abs(candidate - state.target_y) > 0.01]
    return rng.choice(distinct or candidates)


def _apply_racer_action(
    *,
    action: ActionKind,
    state: _RacerState,
    tick: int,
    lane_step: float,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if action is ActionKind.GET_UP:
        if state.status is not RacerStatus.FALLEN or tick < state.state_change_available_at:
            return
        state.status = RacerStatus.RUNNING
        state.rotation = 0.0
        state.facing = 1
        state.cooldown_until = tick + round(0.45 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.RECOVER,
                racer=state,
                message=f"{state.profile.name} finally found the get-up action!",
            )
        )
        return

    if action is ActionKind.TURN:
        if state.status not in {
            RacerStatus.RUNNING,
            RacerStatus.BACKWARDS,
            RacerStatus.FALLEN,
        }:
            return
        state.target_y = _turn_destination(
            state=state,
            lane_step=lane_step,
            rng=rng,
        )
        if state.status is RacerStatus.FALLEN:
            message = f"{state.profile.name} crawled sideways into another lane!"
        elif state.status is RacerStatus.BACKWARDS:
            message = f"{state.profile.name} turned sideways but kept running backwards!"
        else:
            message = f"{state.profile.name} wandered into somebody else's lane!"
        events.append(
            _event(
                tick=tick,
                kind=EventKind.LANE_DRIFT,
                racer=state,
                message=message,
            )
        )
        return

    if action is ActionKind.STUMBLE:
        if (
            state.status not in {RacerStatus.RUNNING, RacerStatus.BACKWARDS}
            or tick < state.state_change_available_at
        ):
            return
        was_knocked_out = _knock_down(
            state=state,
            tick=tick,
            impact=0.35 + state.profile.chaos * 0.25,
            rng=rng,
            config=config,
        )
        if not was_knocked_out:
            _consume_recovery_brew(state=state, tick=tick, events=events)
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

    if action is ActionKind.GO_WRONG_WAY:
        if state.status is not RacerStatus.RUNNING or tick < state.state_change_available_at:
            return
        state.status = RacerStatus.BACKWARDS
        state.facing = -1
        state.state_change_available_at = tick + round(
            (0.9 + state.profile.chaos * 0.6) * config.tick_rate
        )
        state.cooldown_until = tick + round(0.4 * config.tick_rate)
        _consume_recovery_brew(state=state, tick=tick, events=events)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.WRONG_WAY,
                racer=state,
                message=f"{state.profile.name} forgot which way the finish line is!",
            )
        )
        return

    if action is ActionKind.TURN_AROUND:
        if state.status is not RacerStatus.BACKWARDS or tick < state.state_change_available_at:
            return
        state.status = RacerStatus.RUNNING
        state.facing = 1
        state.rotation = 0.0
        state.state_change_available_at = tick + round(0.75 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.TURN_AROUND,
                racer=state,
                message=f"{state.profile.name} remembered which way time flows!",
            )
        )
        return

    raise ValueError(f"Unsupported state action: {action}")


def _maybe_take_state_action(
    *,
    state: _RacerState,
    tick: int,
    lane_step: float,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if state.action is not None:
        return
    action = _choose_racer_action(state=state, rng=rng, config=config)
    if action is None:
        return
    state.action = action
    _apply_racer_action(
        action=action,
        state=state,
        tick=tick,
        lane_step=lane_step,
        rng=rng,
        config=config,
        events=events,
    )


def _refresh_action_state(state: _RacerState, tick: int) -> None:
    if tick >= state.speed_multiplier_until:
        state.speed_multiplier = 1.0
    if state.status is not RacerStatus.RUNNING:
        return
    if tick < state.showboat_until:
        state.rotation = 14.0 if (tick // 3) % 2 == 0 else -14.0
    else:
        state.rotation = 0.0


def _set_temporary_speed(
    state: _RacerState,
    *,
    multiplier: float,
    until: int,
) -> None:
    state.speed_multiplier = multiplier
    state.speed_multiplier_until = until


def _start_showboat(
    *,
    state: _RacerState,
    tick: int,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    duration_seconds = rng.uniform(*_SHOWBOAT_DURATION_SECONDS)
    duration_ticks = max(round(duration_seconds * config.tick_rate), 1)
    showboat_until = tick + duration_ticks
    state.action = ActionKind.SHOWBOAT
    _set_temporary_speed(
        state,
        multiplier=_SHOWBOAT_SPEED_MULTIPLIER,
        until=showboat_until,
    )
    state.showboat_until = showboat_until
    state.action_cooldown_until = tick + round(8.0 * config.tick_rate)
    reason = rng.choice(_SHOWBOAT_REASONS)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.SHOWBOAT,
            racer=state,
            message=f"{state.profile.name} {reason}",
        )
    )


def _maybe_race_action(
    *,
    state: _RacerState,
    states: list[_RacerState],
    tick: int,
    lane_step: float,
    rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    if (
        state.status is not RacerStatus.RUNNING
        or state.action is not None
        or tick < state.action_cooldown_until
        or state.x < config.start_x + 0.04
        or state.x > config.finish_x - 0.06
        or config.action_scale <= 0
        or config.chaos_scale <= 0
    ):
        return

    event_rate = (
        (
            0.035
            + state.profile.chaos * 0.035
            + state.profile.recovery * 0.018
            + state.profile.aggression * 0.022
        )
        * config.action_scale
        * min(config.chaos_scale, 3.0)
        * _pace_frequency_scale(config)
    )
    if rng.random() >= min(event_rate, 1.2) / config.tick_rate:
        return

    roll = rng.random()
    if roll < 0.24 and state.x > 0.24:
        _start_showboat(
            state=state,
            tick=tick,
            rng=rng,
            config=config,
            events=events,
        )
        return

    if roll < 0.46:
        state.action = ActionKind.PORTAL_HOP
        direction = -1 if rng.random() < 0.5 else 1
        destination = min(max(state.base_y + direction * lane_step, 0.12), 0.88)
        state.y = destination
        state.target_y = destination
        state.x = min(
            state.x + 0.012 + state.profile.recovery * 0.008,
            config.finish_x - 0.02,
        )
        state.action_cooldown_until = tick + round(11.0 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.PORTAL_HOP,
                racer=state,
                message=f"{state.profile.name} found an unauthorized subspace shortcut!",
            )
        )
        return

    if roll < 0.68 and state.damage >= 0.55 and not state.second_wind_used:
        state.action = ActionKind.SECOND_WIND
        state.second_wind_used = True
        state.damage = max(state.damage - 0.35, 0.0)
        duration_ticks = round(2.0 * config.tick_rate)
        _set_temporary_speed(
            state,
            multiplier=1.18 + state.profile.recovery * 0.08,
            until=tick + duration_ticks,
        )
        state.action_cooldown_until = tick + round(10.0 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.SECOND_WIND,
                racer=state,
                message=f"{state.profile.name} activated a suspiciously heroic second wind!",
            )
        )
        return

    active_positions = [
        candidate.x
        for candidate in states
        if candidate.status
        in {
            RacerStatus.RUNNING,
            RacerStatus.BACKWARDS,
            RacerStatus.FALLEN,
        }
    ]
    midpoint = sorted(active_positions)[len(active_positions) // 2]
    if state.x < midpoint:
        state.action = ActionKind.PANIC_SPRINT
        duration_ticks = round(1.6 * config.tick_rate)
        _set_temporary_speed(
            state,
            multiplier=1.16 + state.profile.aggression * 0.10,
            until=tick + duration_ticks,
        )
        state.action_cooldown_until = tick + round(8.0 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.PANIC_SPRINT,
                racer=state,
                message=f"{state.profile.name} remembered the finish line has snacks!",
            )
        )
        return

    state.action = ActionKind.EVASIVE_JUKE
    state.target_y = min(
        max(state.base_y + (-1 if rng.random() < 0.5 else 1) * lane_step * 0.45, 0.12),
        0.88,
    )
    state.x = max(config.start_x * 0.5, state.x - 0.003)
    state.action_cooldown_until = tick + round(5.0 * config.tick_rate)
    events.append(
        _event(
            tick=tick,
            kind=EventKind.EVASIVE_JUKE,
            racer=state,
            message=f"{state.profile.name} juked using improbable geometry!",
        )
    )


def _move_racer(
    *,
    state: _RacerState,
    rng: random.Random,
    config: SimulationConfig,
    finish_sprint_active: bool = False,
    tick: int = 0,
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

    speed_wobble = 0.94 + rng.random() * 0.12
    speed = (
        config.base_track_speed
        * state.profile.base_speed
        * speed_wobble
        * state.speed_multiplier
        * _nitro_speed_multiplier(state, tick)
        * (config.finish_sprint_multiplier if finish_sprint_active else 1.0)
    )
    if state.status is RacerStatus.FALLEN:
        state.facing = 1
        state.x = min(state.x + speed * dt * 0.5, config.finish_x)
        return
    if state.status is RacerStatus.BACKWARDS:
        state.facing = -1
        state.x = max(config.start_x * 0.35, state.x - speed * dt * 0.55)
        return

    state.x += speed * dt


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
    size_advantage = max(runner.visual_scale - fallen.visual_scale, 0.0)
    stomp_chance = (
        0.09 + runner.profile.aggression * 0.15 + size_advantage * 0.08
    ) * config.chaos_scale
    if rng.random() >= stomp_chance:
        return False

    runner.cooldown_until = tick + round(0.5 * config.tick_rate)
    _destroy_racer(
        state=fallen,
        tick=tick,
        finish_x=config.finish_x,
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
    action_rng: random.Random,
    config: SimulationConfig,
    events: list[RaceEvent],
) -> None:
    active = {RacerStatus.RUNNING, RacerStatus.BACKWARDS, RacerStatus.FALLEN}
    if first.status not in active or second.status not in active:
        return
    collision_scale = _clamp((first.visual_scale + second.visual_scale) / 2.0, 0.65, 1.4)
    if (
        abs(first.x - second.x) > 0.024 * collision_scale
        or abs(first.y - second.y) > 0.042 * collision_scale
    ):
        return
    first_phased = _consume_ghost_draught(
        state=first,
        tick=tick,
        events=events,
    )
    second_phased = _consume_ghost_draught(
        state=second,
        tick=tick,
        events=events,
    )
    if first_phased or second_phased:
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
        (0.75 + (first.profile.aggression + second.profile.aggression) * 0.75)
        * config.chaos_scale
        * _pace_frequency_scale(config)
    )
    if rng.random() >= collision_rate / config.tick_rate:
        return

    total_aggression = first.profile.aggression + second.profile.aggression + 0.1
    attacker = (
        first if rng.random() < (first.profile.aggression + 0.05) / total_aggression else second
    )
    victim = second if attacker is first else first
    juke_chance = (0.035 + victim.profile.recovery * 0.10) * config.action_scale
    if (
        victim.status is RacerStatus.RUNNING
        and victim.action is None
        and tick >= victim.action_cooldown_until
        and config.action_scale > 0
        and action_rng.random() < min(juke_chance, 0.3)
    ):
        victim.action = ActionKind.EVASIVE_JUKE
        if abs(victim.y - attacker.y) < 0.005:
            direction = -1 if action_rng.random() < 0.5 else 1
        else:
            direction = -1 if victim.y < attacker.y else 1
        victim.target_y = min(max(victim.y + direction * 0.08, 0.12), 0.88)
        victim.x = max(config.start_x * 0.5, victim.x - 0.004)
        victim.action_cooldown_until = tick + round(6.0 * config.tick_rate)
        events.append(
            _event(
                tick=tick,
                kind=EventKind.EVASIVE_JUKE,
                racer=victim,
                target=attacker,
                message=(
                    f"{victim.profile.name} dodged {attacker.profile.name} "
                    "with improbable geometry!"
                ),
            )
        )
        return

    impact = 0.55 + attacker.profile.aggression * 0.65
    victim_knocked_out = _knock_down(
        state=victim,
        tick=tick,
        impact=impact,
        rng=rng,
        config=config,
    )
    if not victim_knocked_out:
        _consume_recovery_brew(state=victim, tick=tick, events=events)
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
        if not attacker_knocked_out:
            _consume_recovery_brew(state=attacker, tick=tick, events=events)
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
    physical_finish_order: list[int],
    finish_ticks: dict[int, int],
    events: list[RaceEvent],
    config: SimulationConfig,
) -> None:
    crossing = [
        state
        for state in states
        if state.status
        in {
            RacerStatus.RUNNING,
            RacerStatus.BACKWARDS,
            RacerStatus.FALLEN,
        }
        and state.x >= config.finish_x
    ]
    crossing.sort(key=lambda state: (-state.x, state.profile.racer_id))
    for state in crossing:
        was_crawling = state.status is RacerStatus.FALLEN
        state.x = config.finish_x
        state.status = RacerStatus.FINISHED
        state.facing = 1
        state.rotation = 0.0
        state.finish_tick = tick
        physical_racer_id = state.profile.racer_id
        official_racer_id = state.profile.identity_racer_id or physical_racer_id
        physical_finish_order.append(physical_racer_id)
        identity_state = next(
            (candidate for candidate in states if candidate.profile.racer_id == official_racer_id),
            None,
        )
        official_finish_place: int | None = None
        if official_racer_id in finish_order:
            state.finish_place = None
            if official_racer_id != physical_racer_id:
                state.status = RacerStatus.DNF
                state.dnf_reason = "identity_stolen"
            identity_name = (
                identity_state.profile.name
                if identity_state is not None
                else "that stolen identity"
            )
            message = (
                f"{state.profile.name} crossed as {identity_name}, "
                "but that identity already had a result!"
            )
        else:
            official_finish_place = len(finish_order) + 1
            finish_order.append(official_racer_id)
            finish_ticks[official_racer_id] = tick
            if official_racer_id != physical_racer_id and identity_state is not None:
                state.status = RacerStatus.DNF
                state.finish_place = None
                state.dnf_reason = "identity_stolen"
                identity_state.x = config.finish_x
                identity_state.status = RacerStatus.FINISHED
                identity_state.facing = 1
                identity_state.rotation = 0.0
                identity_state.finish_tick = tick
                identity_state.finish_place = official_finish_place
                identity_state.dnf_reason = ""
                message = (
                    f"{state.profile.name} crossed as {identity_state.profile.name}! "
                    f"Place {official_finish_place} belongs to {identity_state.profile.name}."
                )
            else:
                state.finish_place = official_finish_place
                message = (
                    f"{state.profile.name} crawled across the line in place {state.finish_place}!"
                    if was_crawling
                    else f"{state.profile.name} finished in place {state.finish_place}!"
                )
        events.append(
            _event(
                tick=tick,
                kind=EventKind.FINISH,
                racer=state,
                target=identity_state if official_racer_id != physical_racer_id else None,
                message=message,
                finish_place=official_finish_place,
            )
        )


def _eliminate_after_finish_deadline(
    *,
    states: list[_RacerState],
    tick: int,
    finish_grace_seconds: int,
    events: list[RaceEvent],
) -> None:
    for state in states:
        if state.status not in {
            RacerStatus.RUNNING,
            RacerStatus.BACKWARDS,
            RacerStatus.FALLEN,
        }:
            continue
        state.status = RacerStatus.DNF
        state.facing = 1
        state.dnf_reason = "finish_countdown"
        state.cooldown_until = tick
        events.append(
            _event(
                tick=tick,
                kind=EventKind.TIMEOUT,
                racer=state,
                message=(
                    f"The {finish_grace_seconds}-second finish clock "
                    f"eliminated {state.profile.name}!"
                ),
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
    if (
        simulation.tick_rate <= 0
        or simulation.duration_seconds <= 0
        or simulation.finish_grace_seconds <= 0
    ):
        raise ValueError("Tick rate, duration, and finish grace must be positive.")
    if simulation.action_scale < 0:
        raise ValueError("Action scale cannot be negative.")
    if simulation.base_track_speed <= 0:
        raise ValueError("Base track speed must be positive.")
    if simulation.finish_sprint_multiplier <= 0:
        raise ValueError("Finish sprint multiplier must be positive.")
    if not 0.0 < simulation.fire_pit_boundary < 0.5:
        raise ValueError("Fire pit boundary must be between zero and one half.")

    active_effects = effects or []
    potion_resolution = _resolve_potion_effects(profiles, active_effects, seed=seed)
    adjusted_profiles = potion_resolution.profiles
    obstacles = _build_obstacles(active_effects)
    scheduled_potions = _schedule_potion_effects(
        effects=potion_resolution.activated_effects,
        seed=seed,
        duration_ticks=simulation.duration_ticks,
    )

    rng = random.Random(seed)
    action_rng = random.Random(seed ^ 0x5A17C0DE)
    lane_step = 1.0 / (len(adjusted_profiles) + 1)
    states = [
        _RacerState(
            profile=profile,
            base_y=(index + 1) * lane_step,
            x=simulation.start_x,
            y=(index + 1) * lane_step,
            target_y=(index + 1) * lane_step,
            visual_scale=potion_resolution.visual_scales.get(profile.racer_id, 1.0),
        )
        for index, profile in enumerate(adjusted_profiles)
    ]
    _initialize_runtime_tonics(
        states=states,
        effects=potion_resolution.activated_effects,
        config=simulation,
    )
    events: list[RaceEvent] = []
    timeline: list[TimelineFrame] = [_frame(0, states, obstacles)]
    finish_order: list[int] = []
    physical_finish_order: list[int] = []
    finish_ticks: dict[int, int] = {}
    finish_deadline_tick: int | None = None
    last_tick = 0
    successful_effect_ids = {
        effect.effect_id
        for effect in potion_resolution.activated_effects
        if effect.kind not in _SCHEDULED_TONIC_KINDS
    }
    failed_effect_ids = {effect.effect_id for effect in potion_resolution.failed_effects}

    if active_effects:
        _potion_tick_one_events(
            effects=active_effects,
            activated_effects=potion_resolution.activated_effects,
            failed_effects=potion_resolution.failed_effects,
            states=states,
            events=events,
        )

    state_by_id = {state.profile.racer_id: state for state in states}

    maximum_tick = simulation.duration_ticks + simulation.finish_grace_ticks
    for tick in range(1, maximum_tick + 1):
        if finish_deadline_tick is None and tick > simulation.duration_ticks:
            break
        last_tick = tick
        finish_sprint_active = finish_deadline_tick is not None
        for state in states:
            state.action = None

        for scheduled in scheduled_potions:
            if scheduled.tick != tick:
                continue
            target_state = state_by_id.get(scheduled.racer_id)
            if target_state is None:
                continue
            activated = _apply_scheduled_potion(
                scheduled=scheduled,
                state=target_state,
                tick=tick,
                lane_step=lane_step,
                config=simulation,
                events=events,
            )
            if activated:
                successful_effect_ids.add(scheduled.effect_id)
                failed_effect_ids.discard(scheduled.effect_id)
            else:
                successful_effect_ids.discard(scheduled.effect_id)
                failed_effect_ids.add(scheduled.effect_id)

        for state in states:
            _refresh_action_state(state, tick)
            _destroy_in_fire_pit(
                state=state,
                tick=tick,
                config=simulation,
                events=events,
            )
            _maybe_take_state_action(
                state=state,
                tick=tick,
                lane_step=lane_step,
                rng=rng,
                config=simulation,
                events=events,
            )
            _move_racer(
                state=state,
                rng=rng,
                config=simulation,
                finish_sprint_active=finish_sprint_active,
                tick=tick,
            )
            # Resolve contact before a shortcut or juke can teleport the racer back to safety.
            _destroy_in_fire_pit(
                state=state,
                tick=tick,
                config=simulation,
                events=events,
            )
            _maybe_trigger_potion_second_wind(
                state=state,
                states=states,
                tick=tick,
                config=simulation,
                events=events,
            )
            _maybe_race_action(
                state=state,
                states=states,
                tick=tick,
                lane_step=lane_step,
                rng=action_rng,
                config=simulation,
                events=events,
            )
            _destroy_in_fire_pit(
                state=state,
                tick=tick,
                config=simulation,
                events=events,
            )

        _apply_roomba_vacuums(
            states=states,
            obstacles=obstacles,
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
                    action_rng=action_rng,
                    config=simulation,
                    events=events,
                )

        _revive_phoenix_states(
            states=states,
            tick=tick,
            config=simulation,
            events=events,
        )
        _mark_finishers(
            states=states,
            tick=tick,
            finish_order=finish_order,
            physical_finish_order=physical_finish_order,
            finish_ticks=finish_ticks,
            events=events,
            config=simulation,
        )
        if finish_deadline_tick is None and finish_order:
            finish_deadline_tick = tick + simulation.finish_grace_ticks
        if finish_deadline_tick is not None and tick >= finish_deadline_tick:
            _eliminate_after_finish_deadline(
                states=states,
                tick=tick,
                finish_grace_seconds=simulation.finish_grace_seconds,
                events=events,
            )

        if tick % simulation.snapshot_every_ticks == 0:
            timeline.append(_frame(tick, states, obstacles))
        if all(
            state.status
            in {
                RacerStatus.FINISHED,
                RacerStatus.KNOCKED_OUT,
                RacerStatus.DESTROYED,
                RacerStatus.DNF,
            }
            for state in states
        ):
            if timeline[-1]["tick"] != tick:
                timeline.append(_frame(tick, states, obstacles))
            break

    final_tick = last_tick
    for state in states:
        if state.status in {
            RacerStatus.FINISHED,
            RacerStatus.KNOCKED_OUT,
            RacerStatus.DESTROYED,
            RacerStatus.DNF,
        }:
            continue
        _destroy_racer(
            state=state,
            tick=final_tick,
            finish_x=simulation.finish_x,
            reason="track_consumed",
            message=f"Closing flames swallowed {state.profile.name}!",
            events=events,
        )

    if timeline[-1]["tick"] == final_tick:
        timeline[-1] = _frame(final_tick, states, obstacles)
    else:
        timeline.append(_frame(final_tick, states, obstacles))

    dnf: list[DnfResult] = [
        {
            "racer_id": state.profile.racer_id,
            "reason": state.dnf_reason or "eliminated",
        }
        for state in states
        if state.profile.racer_id not in finish_ticks
    ]
    tonic_effect_ids = {
        effect.effect_id for effect in active_effects if effect.kind in _TONIC_KINDS
    }
    failed_effect_ids.update(tonic_effect_ids - successful_effect_ids)
    return SimulationResult(
        seed=seed,
        tick_rate=simulation.tick_rate,
        duration_ticks=final_tick,
        finish_deadline_tick=finish_deadline_tick,
        timeline=timeline,
        events=events,
        finish_order=finish_order,
        physical_finish_order=physical_finish_order,
        finish_ticks=finish_ticks,
        identity_racer_ids={
            profile.racer_id: profile.identity_racer_id
            for profile in adjusted_profiles
            if profile.identity_racer_id is not None
        },
        dnf=dnf,
        successful_effect_ids=[
            effect.effect_id
            for effect in active_effects
            if effect.effect_id in successful_effect_ids
        ],
        failed_effect_ids=[
            effect.effect_id for effect in active_effects if effect.effect_id in failed_effect_ids
        ],
    )
