from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.db import OperationalError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.betting.services import settle_round
from apps.racing.effects import build_race_effects, serialize_effects
from apps.racing.models import Race, RaceEntry, Racer, RoomSettings, Round, RoundItemUse
from apps.racing.serializers import build_live_state
from apps.racing.sim.engine import simulate_race
from apps.racing.sim.profiles import derive_fixed_odds
from apps.racing.sim.types import RacerProfile, SimulationConfig

LOGGER = logging.getLogger(__name__)
LIVE_GROUP = "game_live"
DISPLAY_GROUP = "game_display"
RACE_PAYLOAD_RETENTION_ROUNDS = 12


@dataclass(slots=True)
class TransitionResult:
    event_names: list[str] = field(default_factory=list)
    changed_balances: dict[int, int] = field(default_factory=dict)


def _profile(racer: Racer) -> RacerProfile:
    return RacerProfile(
        racer_id=racer.pk,
        name=racer.name,
        sprite_key=racer.sprite_key,
        color=racer.color,
        base_speed=racer.base_speed,
        resilience=racer.resilience,
        recovery=racer.recovery,
        aggression=racer.aggression,
        chaos=racer.chaos,
    )


def _prune_old_race_payloads(
    current_round_number: int,
    *,
    keep_rounds: int = RACE_PAYLOAD_RETENTION_ROUNDS,
) -> int:
    cutoff = current_round_number - keep_rounds
    if cutoff <= 0:
        return 0
    return (
        Race.objects.filter(round__number__lte=cutoff)
        .exclude(timeline=[], events=[])
        .update(timeline=[], events=[])
    )


def _create_round(now: datetime, room: RoomSettings) -> Round:
    active_racers = list(Racer.objects.filter(active=True).order_by("sort_order", "name"))
    if len(active_racers) < 2:
        raise RuntimeError("At least two active racers are required.")

    roster_size = min(room.runner_count, len(active_racers))
    roster = active_racers[:roster_size]
    profiles = [_profile(racer) for racer in roster]
    odds = derive_fixed_odds(profiles)
    next_number = (Round.objects.aggregate(number=Max("number"))["number"] or 0) + 1

    locks_at = now + timedelta(seconds=room.betting_seconds)
    race_starts_at = locks_at + timedelta(seconds=room.lineup_seconds)
    race_ends_at = race_starts_at + timedelta(seconds=room.race_seconds)
    results_end_at = race_ends_at + timedelta(seconds=room.results_seconds)
    current_round = Round.objects.create(
        number=next_number,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=locks_at,
        race_starts_at=race_starts_at,
        race_ends_at=race_ends_at,
        results_end_at=results_end_at,
    )
    race = Race.objects.create(round=current_round, tick_rate=20)
    RaceEntry.objects.bulk_create(
        [
            RaceEntry(
                race=race,
                racer=racer,
                lane=lane,
                odds=odds[racer.pk],
            )
            for lane, racer in enumerate(roster, start=1)
        ]
    )
    _prune_old_race_payloads(current_round.number)
    return current_round


def _generate_race(current_round: Round, room: RoomSettings, now: datetime) -> None:
    race = Race.objects.select_for_update().get(round=current_round)
    entries = list(race.entries.select_related("racer").order_by("lane"))
    profiles = [_profile(entry.racer) for entry in entries]
    item_uses = list(
        RoundItemUse.objects.filter(round=current_round)
        .select_related("player", "item", "target_entry__racer")
        .order_by("created_at", "pk")
    )
    effects = build_race_effects(item_uses)
    race.inputs = {"effects": serialize_effects(effects)}
    seed = secrets.randbits(63)
    result = simulate_race(
        profiles,
        seed=seed,
        config=SimulationConfig(
            tick_rate=race.tick_rate,
            duration_seconds=room.race_seconds,
        ),
        effects=effects,
    )

    race.seed = seed
    race.duration_ticks = result.duration_ticks
    race.timeline = result.timeline
    race.events = result.events
    race.result = {
        "finish_order": result.finish_order,
        "finish_ticks": result.finish_ticks,
        "dnf": result.dnf,
        "house_wins": not result.finish_order,
    }
    race.generated_at = now
    race.completed_at = now
    race.save(
        update_fields=[
            "inputs",
            "seed",
            "duration_ticks",
            "timeline",
            "events",
            "result",
            "generated_at",
            "completed_at",
        ]
    )

    finish_places = {
        racer_id: place for place, racer_id in enumerate(result.finish_order, start=1)
    }
    finish_ticks = result.finish_ticks
    dnf_reasons = {item["racer_id"]: item["reason"] for item in result.dnf}
    for entry in entries:
        entry.finish_place = finish_places.get(entry.racer_id)
        entry.finish_tick = finish_ticks.get(entry.racer_id)
        entry.dnf_reason = dnf_reasons.get(entry.racer_id, "")
    RaceEntry.objects.bulk_update(entries, ["finish_place", "finish_tick", "dnf_reason"])

    playback_seconds = max(result.duration_ticks / race.tick_rate, 5.0)
    current_round.race_ends_at = current_round.race_starts_at + timedelta(
        seconds=playback_seconds
    )
    current_round.results_end_at = current_round.race_ends_at + timedelta(
        seconds=room.results_seconds
    )


@transaction.atomic
def advance_once(now: datetime | None = None) -> TransitionResult:
    current_time = now or timezone.now()
    room = RoomSettings.objects.select_for_update().get_or_create(pk=1)[0]
    if room.is_paused:
        return TransitionResult()

    current_round = Round.objects.select_for_update().order_by("-number").first()
    if current_round is None:
        _create_round(current_time, room)
        return TransitionResult(event_names=["round.opened"])

    if current_round.state == Round.State.OPEN and current_time >= current_round.locks_at:
        _generate_race(current_round, room, current_time)
        current_round.state = Round.State.LOCKED
        current_round.save(
            update_fields=["state", "race_ends_at", "results_end_at"],
        )
        return TransitionResult(event_names=["round.locked"])

    if (
        current_round.state == Round.State.LOCKED
        and current_time >= current_round.race_starts_at
    ):
        current_round.state = Round.State.RACING
        current_round.save(update_fields=["state"])
        return TransitionResult(event_names=["race.started"])

    if (
        current_round.state == Round.State.RACING
        and current_time >= current_round.race_ends_at
    ):
        current_round.state = Round.State.RESULTS
        current_round.save(update_fields=["state"])
        balances = settle_round(current_round.pk)
        return TransitionResult(
            event_names=["race.finished"],
            changed_balances=balances,
        )

    if (
        current_round.state == Round.State.RESULTS
        and current_time >= current_round.results_end_at
    ):
        _create_round(current_time, room)
        return TransitionResult(event_names=["round.opened"])

    return TransitionResult()


async def _send_group(group: str, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RuntimeError("The default Channels layer is not configured.")
    await channel_layer.group_send(
        group,
        {
            "type": "game.message",
            "payload": payload,
        },
    )


async def broadcast_current_state(
    event_name: str,
    *,
    include_timeline: bool = True,
) -> None:
    public_state, display_state = await asyncio.gather(
        sync_to_async(build_live_state, thread_sensitive=True)(),
        sync_to_async(build_live_state, thread_sensitive=True)(
            include_timeline=include_timeline
        ),
    )
    await asyncio.gather(
        _send_group(LIVE_GROUP, {"type": event_name, "state": public_state}),
        _send_group(DISPLAY_GROUP, {"type": event_name, "state": display_state}),
    )


class RoundCoordinator:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="round-coordinator")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def run(self) -> None:
        while True:
            try:
                result = await sync_to_async(advance_once, thread_sensitive=True)()
                for event_name in result.event_names:
                    await broadcast_current_state(event_name)
                for player_id, balance_cents in result.changed_balances.items():
                    await _send_group(
                        f"player_{player_id}",
                        {
                            "type": "balance.updated",
                            "balance_cents": balance_cents,
                        },
                    )
            except OperationalError:
                LOGGER.exception("Race coordinator is waiting for the database.")
            except Exception:
                LOGGER.exception("Race coordinator transition failed.")
            await asyncio.sleep(0.25)


coordinator = RoundCoordinator()
