from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NotRequired, TypedDict


class ActionKind(StrEnum):
    GET_UP = "get_up"
    TURN = "turn"
    STUMBLE = "stumble"
    GO_WRONG_WAY = "go_wrong_way"
    TURN_AROUND = "turn_around"
    SHOWBOAT = "showboat"
    PORTAL_HOP = "portal_hop"
    SECOND_WIND = "second_wind"
    EVASIVE_JUKE = "evasive_juke"
    PANIC_SPRINT = "panic_sprint"


class RacerStatus(StrEnum):
    RUNNING = "running"
    BACKWARDS = "backwards"
    FALLEN = "fallen"
    FINISHED = "finished"
    KNOCKED_OUT = "knocked_out"
    DESTROYED = "destroyed"
    DNF = "dnf"


class EventKind(StrEnum):
    START = "start"
    STUMBLE = "stumble"
    WRONG_WAY = "wrong_way"
    LANE_DRIFT = "lane_drift"
    BODY_CHECK = "body_check"
    STOMP = "stomp"
    PILEUP = "pileup"
    RECOVER = "recover"
    KNOCKOUT = "knockout"
    FINISH = "finish"
    TIMEOUT = "timeout"
    POTION_USED = "potion_used"
    POTION_TRIGGERED = "potion_triggered"
    POTION_FIZZLED = "potion_fizzled"
    OBSTACLE_HIT = "obstacle_hit"
    DESTROYED = "destroyed"
    SHOWBOAT = "showboat"
    PORTAL_HOP = "portal_hop"
    SECOND_WIND = "second_wind"
    EVASIVE_JUKE = "evasive_juke"
    PANIC_SPRINT = "panic_sprint"
    TURN_AROUND = "turn_around"


@dataclass(frozen=True, slots=True)
class RaceEffect:
    kind: str
    strength: float
    effect_id: int = 0
    item_name: str = ""
    item_icon: str = ""
    item_color: str = "#ffffff"
    buyer: str = ""
    racer_id: int | None = None
    lane: float | None = None
    position: float | None = None
    activation_tick: int = 0


@dataclass(frozen=True, slots=True)
class RacerProfile:
    racer_id: int
    name: str
    sprite_key: str
    color: str
    base_speed: float
    resilience: float
    recovery: float
    aggression: float
    chaos: float
    identity_racer_id: int | None = None


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    tick_rate: int = 20
    duration_seconds: int = 120
    finish_grace_seconds: int = 30
    start_x: float = 0.055
    finish_x: float = 0.945
    base_track_speed: float = 0.045
    snapshot_every_ticks: int = 2
    chaos_scale: float = 1.0
    action_scale: float = 1.0
    knockout_scale: float = 1.0
    fire_pit_boundary: float = 0.1

    @property
    def duration_ticks(self) -> int:
        return self.tick_rate * self.duration_seconds

    @property
    def finish_grace_ticks(self) -> int:
        return self.tick_rate * self.finish_grace_seconds


class RacerFrame(TypedDict):
    id: int
    x: float
    y: float
    state: str
    facing: int
    rotation: float
    scale: float
    sprite_key: str
    place: int | None


class TimelineFrame(TypedDict):
    tick: int
    racers: list[RacerFrame]


class RaceEvent(TypedDict):
    tick: int
    kind: str
    racer_id: int
    message: str
    target_id: NotRequired[int]
    effect_id: NotRequired[int]


class DnfResult(TypedDict):
    racer_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationResult:
    seed: int
    tick_rate: int
    duration_ticks: int
    finish_deadline_tick: int | None
    timeline: list[TimelineFrame]
    events: list[RaceEvent]
    finish_order: list[int]
    physical_finish_order: list[int]
    finish_ticks: dict[int, int]
    identity_racer_ids: dict[int, int]
    dnf: list[DnfResult]
    successful_effect_ids: list[int]
    failed_effect_ids: list[int]
