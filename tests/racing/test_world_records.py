from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from importlib import import_module

import pytest
from apps.racing.models import (
    Race,
    RaceEntry,
    Racer,
    RacerWorldRecord,
    Round,
)
from apps.racing.world_records import (
    extract_world_record_candidates,
    format_world_record_value,
    racer_world_record_cards,
    update_world_records,
    world_record_cards,
)
from django.apps import apps as django_apps
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _settled_race(
    *,
    number: int,
    first: Racer,
    second: Racer,
    first_finish_tick: int | None,
    second_finish_tick: int | None,
    timeline: list[dict[str, object]] | None = None,
    events: list[dict[str, object]] | None = None,
) -> Race:
    now = timezone.now()
    current_round = Round.objects.create(
        number=number,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=3),
        locks_at=now - timedelta(minutes=2),
        race_starts_at=now - timedelta(minutes=1),
        race_ends_at=now,
        results_end_at=now + timedelta(seconds=20),
        settled_at=now,
    )
    race = Race.objects.create(
        round=current_round,
        tick_rate=20,
        duration_ticks=120,
        timeline=timeline or [],
        events=events or [],
        completed_at=now,
    )
    finishers = [
        (racer, finish_tick)
        for racer, finish_tick in (
            (first, first_finish_tick),
            (second, second_finish_tick),
        )
        if finish_tick is not None
    ]
    finishers.sort(key=lambda item: item[1])
    places = {
        racer.pk: index
        for index, (racer, _finish_tick) in enumerate(
            finishers,
            start=1,
        )
    }
    for lane, (racer, finish_tick) in enumerate(
        (
            (first, first_finish_tick),
            (second, second_finish_tick),
        ),
        start=1,
    ):
        RaceEntry.objects.create(
            race=race,
            racer=racer,
            lane=lane,
            odds=Decimal("4.00"),
            finish_place=places.get(racer.pk),
            finish_tick=finish_tick,
            dnf_reason="" if finish_tick is not None else "finish_countdown",
        )
    return race


def _frame(
    tick: int,
    first: Racer,
    first_state: str,
    second: Racer,
    second_state: str,
) -> dict[str, object]:
    return {
        "tick": tick,
        "racers": [
            {"id": first.pk, "state": first_state},
            {"id": second.pk, "state": second_state},
        ],
    }


def test_extracts_all_supported_single_race_metrics() -> None:
    first = Racer.objects.create(
        name="First",
        slug="first-record-racer",
        sprite_key="skeleton",
    )
    second = Racer.objects.create(
        name="Second",
        slug="second-record-racer",
        sprite_key="mushroom",
    )
    timeline = [
        _frame(0, first, "running", second, "running"),
        _frame(20, first, "fallen", second, "running"),
        _frame(40, first, "fallen", second, "fallen"),
        _frame(60, first, "running", second, "running"),
        _frame(80, first, "fallen", second, "running"),
        _frame(100, first, "running", second, "finished"),
    ]
    events = [
        {"tick": 10, "kind": "wrong_way", "racer_id": first.pk},
        {"tick": 12, "kind": "wrong_way", "racer_id": first.pk},
        {"tick": 61, "kind": "recover", "racer_id": first.pk},
        {"tick": 101, "kind": "recover", "racer_id": first.pk},
        {"tick": 72, "kind": "showboat", "racer_id": second.pk},
    ]
    race = _settled_race(
        number=1,
        first=first,
        second=second,
        first_finish_tick=110,
        second_finish_tick=90,
        timeline=timeline,
        events=events,
    )

    candidates = {
        candidate.metric: candidate
        for candidate in extract_world_record_candidates(race)
    }

    assert candidates[RacerWorldRecord.Metric.FASTEST_FINISH].race_entry.racer == second
    assert candidates[RacerWorldRecord.Metric.FASTEST_FINISH].value == 4_500
    assert candidates[RacerWorldRecord.Metric.MOST_FALLS].race_entry.racer == first
    assert candidates[RacerWorldRecord.Metric.MOST_FALLS].value == 2
    assert candidates[RacerWorldRecord.Metric.LONGEST_CRAWL].value == 3_000
    assert candidates[RacerWorldRecord.Metric.MOST_WRONG_WAY].value == 2
    assert candidates[RacerWorldRecord.Metric.MOST_RECOVERIES].value == 2
    assert candidates[RacerWorldRecord.Metric.MOST_SHOWBOATS].race_entry.racer == second


def test_records_require_strict_improvement_and_ties_keep_the_holder() -> None:
    original = Racer.objects.create(
        name="Original",
        slug="original-holder",
        sprite_key="skeleton",
    )
    challenger = Racer.objects.create(
        name="Challenger",
        slug="record-challenger",
        sprite_key="goblin",
    )
    first_race = _settled_race(
        number=1,
        first=challenger,
        second=original,
        first_finish_tick=None,
        second_finish_tick=100,
    )
    tie_race = _settled_race(
        number=2,
        first=challenger,
        second=original,
        first_finish_tick=100,
        second_finish_tick=None,
    )
    better_race = _settled_race(
        number=3,
        first=challenger,
        second=original,
        first_finish_tick=90,
        second_finish_tick=None,
    )

    first_updates = update_world_records(first_race)
    tie_updates = update_world_records(tie_race)
    tied_record = RacerWorldRecord.objects.get(
        metric=RacerWorldRecord.Metric.FASTEST_FINISH
    )
    better_updates = update_world_records(better_race)
    improved_record = RacerWorldRecord.objects.get(
        metric=RacerWorldRecord.Metric.FASTEST_FINISH
    )

    assert len(first_updates) == 1
    assert tie_updates == []
    assert tied_record.racer == original
    assert improved_record.racer == challenger
    assert improved_record.value == 4_500
    assert better_updates[0].previous_racer_name == original.name


def test_record_cards_include_vacancies_and_racer_associations() -> None:
    holder = Racer.objects.create(
        name="Holder",
        slug="record-holder",
        sprite_key="flying-eye",
    )
    other = Racer.objects.create(
        name="Other",
        slug="other-racer",
        sprite_key="mushroom",
    )
    race = _settled_race(
        number=1,
        first=holder,
        second=other,
        first_finish_tick=80,
        second_finish_tick=100,
    )
    update_world_records(race)

    cards = world_record_cards()
    held = racer_world_record_cards(holder.pk)

    assert len(cards) == len(RacerWorldRecord.Metric.choices)
    assert sum(card.record is None for card in cards) == len(cards) - 1
    assert [card.definition.metric for card in held] == [
        RacerWorldRecord.Metric.FASTEST_FINISH
    ]
    assert format_world_record_value(
        RacerWorldRecord.Metric.FASTEST_FINISH,
        4_000,
    ) == "4 seconds"


def test_historical_seed_rebuilds_records_from_retained_race_payloads() -> None:
    archive_ace = Racer.objects.create(
        name="Archive Ace",
        slug="archive-ace",
        sprite_key="bat",
    )
    opponent = Racer.objects.create(
        name="Archive Rival",
        slug="archive-rival",
        sprite_key="slime",
    )
    race = _settled_race(
        number=1,
        first=archive_ace,
        second=opponent,
        first_finish_tick=80,
        second_finish_tick=100,
        events=[
            {
                "tick": 12,
                "kind": "showboat",
                "racer_id": archive_ace.pk,
            }
        ],
        timeline=[
            _frame(
                0,
                archive_ace,
                "running",
                opponent,
                "running",
            ),
            _frame(
                20,
                archive_ace,
                "fallen",
                opponent,
                "running",
            ),
            _frame(
                60,
                archive_ace,
                "running",
                opponent,
                "running",
            ),
        ],
    )
    race.result = {
        "finishers": [
            {
                "racer_id": archive_ace.pk,
                "finish_tick": 80,
            },
            {
                "racer_id": opponent.pk,
                "finish_tick": 100,
            },
        ],
        "dnfs": [],
    }
    race.save(update_fields=["result"])
    migration = import_module(
        "apps.racing.migrations.0017_seed_racer_world_records"
    )

    migration._seed_records(django_apps, None)

    records = RacerWorldRecord.objects.filter(racer=archive_ace)
    assert records.filter(
        metric=RacerWorldRecord.Metric.FASTEST_FINISH,
        value=4_000,
    ).exists()
    assert records.filter(
        metric=RacerWorldRecord.Metric.LONGEST_CRAWL,
        value=2_000,
    ).exists()
    assert records.filter(
        metric=RacerWorldRecord.Metric.MOST_SHOWBOATS,
        value=1,
    ).exists()
