from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from django.db import transaction

from apps.racing.models import Race, RaceEntry, RacerWorldRecord

MetricDirection = Literal["min", "max"]


@dataclass(frozen=True, slots=True)
class WorldRecordDefinition:
    metric: str
    label: str
    description: str
    direction: MetricDirection
    unit: Literal["milliseconds", "count"]


WORLD_RECORD_DEFINITIONS: tuple[WorldRecordDefinition, ...] = (
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.FASTEST_FINISH,
        label="Fastest official finish",
        description="Shortest time from the horn to an official finish.",
        direction="min",
        unit="milliseconds",
    ),
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.MOST_FALLS,
        label="Most falls in one race",
        description="Most separate trips into a crawling state during one race.",
        direction="max",
        unit="count",
    ),
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.LONGEST_CRAWL,
        label="Longest crawl in one race",
        description="Most total time spent crawling during one race.",
        direction="max",
        unit="milliseconds",
    ),
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.MOST_WRONG_WAY,
        label="Most wrong-way episodes",
        description="Most wrong-way incidents during one race.",
        direction="max",
        unit="count",
    ),
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.MOST_RECOVERIES,
        label="Most recoveries",
        description="Most recorded recoveries during one race.",
        direction="max",
        unit="count",
    ),
    WorldRecordDefinition(
        metric=RacerWorldRecord.Metric.MOST_SHOWBOATS,
        label="Most showboats",
        description="Most showboating incidents during one race.",
        direction="max",
        unit="count",
    ),
)
WORLD_RECORD_BY_METRIC = {
    definition.metric: definition for definition in WORLD_RECORD_DEFINITIONS
}


@dataclass(frozen=True, slots=True)
class RecordCandidate:
    metric: str
    race_entry: RaceEntry
    value: int


@dataclass(frozen=True, slots=True)
class NewWorldRecord:
    metric: str
    label: str
    description: str
    value: int
    display_value: str
    racer_id: int
    racer_name: str
    racer_slug: str
    sprite_key: str
    color: str
    round_number: int
    previous_racer_name: str | None
    previous_display_value: str | None


@dataclass(frozen=True, slots=True)
class WorldRecordCard:
    definition: WorldRecordDefinition
    record: RacerWorldRecord | None
    display_value: str | None


def _milliseconds(ticks: int, tick_rate: int) -> int:
    if tick_rate <= 0:
        return 0
    return max((ticks * 1_000 + tick_rate // 2) // tick_rate, 0)


def format_world_record_value(metric: str, value: int) -> str:
    definition = WORLD_RECORD_BY_METRIC[metric]
    if definition.unit == "milliseconds":
        seconds = value / 1_000
        return f"{seconds:.2f}".rstrip("0").rstrip(".") + " seconds"
    return f"{value} time" + ("" if value == 1 else "s")


def _event_counts(race: Race) -> dict[str, Counter[int]]:
    counts: dict[str, Counter[int]] = {
        RacerWorldRecord.Metric.MOST_WRONG_WAY: Counter(),
        RacerWorldRecord.Metric.MOST_RECOVERIES: Counter(),
        RacerWorldRecord.Metric.MOST_SHOWBOATS: Counter(),
    }
    metric_by_kind = {
        "wrong_way": RacerWorldRecord.Metric.MOST_WRONG_WAY,
        "recover": RacerWorldRecord.Metric.MOST_RECOVERIES,
        "showboat": RacerWorldRecord.Metric.MOST_SHOWBOATS,
    }
    for event in race.events or []:
        if not isinstance(event, dict):
            continue
        kind = event.get("kind")
        metric = metric_by_kind.get(kind) if isinstance(kind, str) else None
        racer_id = event.get("racer_id")
        if metric is not None and isinstance(racer_id, int):
            counts[metric][racer_id] += 1
    return counts


def _timeline_counts(race: Race) -> tuple[Counter[int], defaultdict[int, int]]:
    frames = sorted(
        (
            frame
            for frame in (race.timeline or [])
            if isinstance(frame, dict) and isinstance(frame.get("tick"), int)
        ),
        key=lambda frame: int(frame["tick"]),
    )
    falls: Counter[int] = Counter()
    crawl_ticks: defaultdict[int, int] = defaultdict(int)
    previous_states: dict[int, str] = {}
    for index, frame in enumerate(frames):
        tick = int(frame["tick"])
        next_tick = (
            int(frames[index + 1]["tick"])
            if index + 1 < len(frames)
            else max(race.duration_ticks, tick)
        )
        interval_ticks = max(next_tick - tick, 0)
        racers = frame.get("racers")
        if not isinstance(racers, list):
            continue
        for racer_frame in racers:
            if not isinstance(racer_frame, dict):
                continue
            racer_id = racer_frame.get("id")
            state = racer_frame.get("state")
            if not isinstance(racer_id, int) or not isinstance(state, str):
                continue
            if state == "fallen":
                crawl_ticks[racer_id] += interval_ticks
                if previous_states.get(racer_id) != "fallen":
                    falls[racer_id] += 1
            previous_states[racer_id] = state
    return falls, crawl_ticks


def _best_count_candidate(
    *,
    metric: str,
    counts: Counter[int] | dict[int, int],
    entries_by_racer: dict[int, RaceEntry],
) -> RecordCandidate | None:
    eligible = [
        (value, racer_id)
        for racer_id, value in counts.items()
        if value > 0 and racer_id in entries_by_racer
    ]
    if not eligible:
        return None
    value, racer_id = max(eligible, key=lambda item: (item[0], -item[1]))
    return RecordCandidate(metric=metric, race_entry=entries_by_racer[racer_id], value=value)


def extract_world_record_candidates(race: Race) -> list[RecordCandidate]:
    entries = list(race.entries.select_related("racer").all())
    entries_by_racer = {entry.racer_id: entry for entry in entries}
    candidates: dict[str, RecordCandidate] = {}

    finishers = [
        entry
        for entry in entries
        if entry.finish_place is not None and entry.finish_tick is not None
    ]
    if finishers:
        fastest = min(
            finishers,
            key=lambda entry: (
                entry.finish_tick if entry.finish_tick is not None else race.duration_ticks,
                entry.racer_id,
            ),
        )
        finish_tick = fastest.finish_tick
        if finish_tick is not None:
            value = _milliseconds(finish_tick, race.tick_rate)
            if value > 0:
                candidates[RacerWorldRecord.Metric.FASTEST_FINISH] = RecordCandidate(
                    metric=RacerWorldRecord.Metric.FASTEST_FINISH,
                    race_entry=fastest,
                    value=value,
                )

    falls, crawl_ticks = _timeline_counts(race)
    falls_candidate = _best_count_candidate(
        metric=RacerWorldRecord.Metric.MOST_FALLS,
        counts=falls,
        entries_by_racer=entries_by_racer,
    )
    if falls_candidate is not None:
        candidates[falls_candidate.metric] = falls_candidate

    crawl_milliseconds = {
        racer_id: _milliseconds(ticks, race.tick_rate)
        for racer_id, ticks in crawl_ticks.items()
    }
    crawl_candidate = _best_count_candidate(
        metric=RacerWorldRecord.Metric.LONGEST_CRAWL,
        counts=crawl_milliseconds,
        entries_by_racer=entries_by_racer,
    )
    if crawl_candidate is not None:
        candidates[crawl_candidate.metric] = crawl_candidate

    for metric, counts in _event_counts(race).items():
        candidate = _best_count_candidate(
            metric=metric,
            counts=counts,
            entries_by_racer=entries_by_racer,
        )
        if candidate is not None:
            candidates[candidate.metric] = candidate

    return [
        candidates[definition.metric]
        for definition in WORLD_RECORD_DEFINITIONS
        if definition.metric in candidates
    ]


def _is_better(definition: WorldRecordDefinition, value: int, existing_value: int) -> bool:
    if definition.direction == "min":
        return value < existing_value
    return value > existing_value


@transaction.atomic
def update_world_records(race: Race) -> list[NewWorldRecord]:
    candidates = extract_world_record_candidates(race)
    if not candidates:
        return []
    existing_by_metric = {
        record.metric: record
        for record in RacerWorldRecord.objects.select_for_update()
        .filter(metric__in=[candidate.metric for candidate in candidates])
        .select_related("racer")
    }
    new_records: list[NewWorldRecord] = []
    for candidate in candidates:
        definition = WORLD_RECORD_BY_METRIC[candidate.metric]
        existing = existing_by_metric.get(candidate.metric)
        if existing is not None and not _is_better(
            definition,
            candidate.value,
            existing.value,
        ):
            continue
        previous_racer_name = existing.racer.name if existing is not None else None
        previous_display_value = (
            format_world_record_value(existing.metric, existing.value)
            if existing is not None
            else None
        )
        if existing is None:
            existing = RacerWorldRecord(metric=candidate.metric)
        existing.racer = candidate.race_entry.racer
        existing.round = race.round
        existing.race_entry = candidate.race_entry
        existing.value = candidate.value
        existing.save()
        racer = candidate.race_entry.racer
        new_records.append(
            NewWorldRecord(
                metric=candidate.metric,
                label=definition.label,
                description=definition.description,
                value=candidate.value,
                display_value=format_world_record_value(
                    candidate.metric,
                    candidate.value,
                ),
                racer_id=racer.pk,
                racer_name=racer.name,
                racer_slug=racer.slug,
                sprite_key=racer.sprite_key,
                color=racer.color,
                round_number=race.round.number,
                previous_racer_name=previous_racer_name,
                previous_display_value=previous_display_value,
            )
        )
    return new_records


def serialize_new_world_record(record: NewWorldRecord) -> dict[str, Any]:
    return {
        "metric": record.metric,
        "label": record.label,
        "description": record.description,
        "value": record.value,
        "display_value": record.display_value,
        "racer_id": record.racer_id,
        "racer_name": record.racer_name,
        "racer_slug": record.racer_slug,
        "sprite_key": record.sprite_key,
        "color": record.color,
        "round_number": record.round_number,
        "previous_racer_name": record.previous_racer_name,
        "previous_display_value": record.previous_display_value,
    }


def world_record_cards() -> list[WorldRecordCard]:
    records = {
        record.metric: record
        for record in RacerWorldRecord.objects.select_related(
            "racer",
            "round",
            "race_entry",
        )
    }
    return [
        WorldRecordCard(
            definition=definition,
            record=records.get(definition.metric),
            display_value=(
                format_world_record_value(definition.metric, records[definition.metric].value)
                if definition.metric in records
                else None
            ),
        )
        for definition in WORLD_RECORD_DEFINITIONS
    ]


def racer_world_record_cards(racer_id: int) -> list[WorldRecordCard]:
    return [
        card
        for card in world_record_cards()
        if card.record is not None and card.record.racer_id == racer_id
    ]
