from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from apps.racing.models import Race, RaceEntry, Racer, Round
from apps.racing.replay_montage import (
    MIN_INFORMATION_STAGE_MS,
    MIN_SPOKEN_STAGE_MS,
    build_replay_montage,
    commentary_duration_ms,
    replay_manifest,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _frame(tick: int, racer_ids: list[int]) -> dict[str, object]:
    return {
        "tick": tick,
        "racers": [
            {
                "id": racer_id,
                "x": min(0.06 + tick / 160 + racer_id * 0.002, 0.96),
                "y": racer_id / 5,
                "state": "running" if tick < 130 else "finished",
                "facing": 1,
                "rotation": 0,
                "scale": 1,
                "sprite_key": "skeleton",
                "place": 1 if racer_id == racer_ids[0] and tick >= 130 else None,
            }
            for racer_id in racer_ids
        ],
    }


def _race(*, house_wins: bool = False) -> Race:
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.RACING,
        opened_at=now - timedelta(minutes=3),
        locks_at=now - timedelta(minutes=2),
        race_starts_at=now - timedelta(minutes=1),
        race_ends_at=now,
        results_end_at=now + timedelta(seconds=8),
    )
    racers = [
        Racer.objects.create(
            name=f"Replay Racer {index}",
            slug=f"replay-racer-{index}",
            sprite_key=("skeleton", "mushroom", "goblin", "flying-eye")[index - 1],
        )
        for index in range(1, 5)
    ]
    racer_ids = [racer.pk for racer in racers]
    events: list[dict[str, object]] = [
        {
            "tick": 24,
            "kind": "body_check",
            "racer_id": racer_ids[1],
            "target_id": racer_ids[2],
            "message": "Racer 2 body-checked Racer 3!",
        },
        {
            "tick": 78,
            "kind": "obstacle_hit",
            "racer_id": racer_ids[3],
            "effect_id": 91,
            "message": "Racer 4 hit the boxing glove!",
        },
        {
            "tick": 79,
            "kind": "obstacle_removed",
            "racer_id": racer_ids[3],
            "effect_id": 91,
            "message": "The boxing glove flew away.",
        },
    ]
    result: dict[str, object] = {
        "finish_order": [],
        "finish_ticks": {},
        "first_finish_tick": None,
        "house_wins": house_wins,
    }
    if not house_wins:
        events.append(
            {
                "tick": 130,
                "kind": "finish",
                "racer_id": racer_ids[0],
                "finish_place": 1,
                "message": "Racer 1 crossed first!",
            }
        )
        result = {
            "finish_order": [racer_ids[0]],
            "finish_ticks": {str(racer_ids[0]): 130},
            "first_finish_tick": 130,
            "house_wins": False,
        }
    race = Race.objects.create(
        round=current_round,
        seed=44,
        tick_rate=20,
        duration_ticks=140,
        timeline=[_frame(tick, racer_ids) for tick in range(0, 141, 2)],
        events=events,
        inputs={
            "effects": [
                {
                    "id": 91,
                    "kind": "boxing_glove",
                    "item_name": "Boxing Glove",
                    "item_icon": "glove",
                    "item_color": "#ff0000",
                    "buyer": "Tester",
                    "strength": 1,
                    "activation_tick": 10,
                    "lane": 4,
                    "position": 0.55,
                }
            ],
            "successful_effect_ids": [],
            "failed_effect_ids": [],
        },
        result=result,
        generated_at=now,
    )
    RaceEntry.objects.bulk_create(
        [
            RaceEntry(
                race=race,
                racer=racer,
                lane=index,
                odds=Decimal("4.00"),
                finish_place=(1 if index == 1 and not house_wins else None),
                finish_tick=(130 if index == 1 and not house_wins else None),
            )
            for index, racer in enumerate(racers, start=1)
        ]
    )
    return race


def test_replay_montage_is_deterministic_compact_and_ends_on_finish() -> None:
    race = _race()

    first = build_replay_montage(race)
    second = build_replay_montage(race)

    assert first == second
    assert len(first["clips"]) == 3
    assert first["clips"][-1]["kind"] == "finish"
    assert first["clips"][-1]["caption"] == "Racer 1 crossed first!"
    assert all(len(clip["timeline"]) <= 32 for clip in first["clips"])
    assert len(json.dumps(first).encode()) < 100_000
    manifest = replay_manifest(first)
    assert manifest["available"] is True
    assert manifest["version"] == 2
    assert manifest["playback_key"] == first["playback_key"]
    assert manifest["clip_count"] == 3
    assert manifest["total_show_ms"] == first["total_show_ms"]
    assert manifest["stages"] == [
        {
            key: stage[key]
            for key in (
                "id",
                "kind",
                "offset_ms",
                "duration_ms",
                "clip_id",
                "clip_index",
                "record_beat",
            )
            if key in stage
        }
        for stage in first["stages"]
    ]
    assert all(stage["duration_ms"] >= MIN_SPOKEN_STAGE_MS for stage in first["stages"])
    assert first["total_show_ms"] == sum(
        stage["duration_ms"] for stage in first["stages"]
    )


def test_replay_montage_tracks_consumed_items_at_clip_start() -> None:
    race = _race()
    race.events.insert(
        0,
        {
            "tick": 12,
            "kind": "obstacle_hit",
            "racer_id": race.entries.order_by("lane")[1].racer_id,
            "effect_id": 91,
            "message": "The glove fired early.",
        },
    )

    montage = build_replay_montage(race)
    later_clips = [clip for clip in montage["clips"] if clip["start_tick"] > 12]

    assert later_clips
    assert all(91 in clip["consumed_effect_ids_at_start"] for clip in later_clips)


def test_replay_montage_uses_house_win_climax_when_nobody_finishes() -> None:
    race = _race(house_wins=True)

    montage = build_replay_montage(race)

    assert montage["clips"][-1]["kind"] == "house_win"
    assert "house wins" in montage["clips"][-1]["caption"].lower()


def test_show_stages_are_conditional_readable_and_potion_aware() -> None:
    race = _race()
    winner = race.entries.get(finish_place=1)
    record_rival = race.entries.exclude(pk=winner.pk).order_by("lane").first()
    assert record_rival is not None
    race.inputs = {
        **race.inputs,
        "effects": [
            *race.inputs["effects"],
            {
                "id": 302,
                "kind": "phoenix_flask",
                "item_name": "Phoenix Flask",
                "item_icon": "🔥",
                "item_color": "#ff7a45",
                "buyer": "Potion Patron",
                "target_racer_id": winner.racer_id,
                "activation_tick": 55,
                "strength": 1,
            },
        ],
        "successful_effect_ids": [302],
    }
    race.events.append(
        {
            "tick": 55,
            "kind": "potion_triggered",
            "racer_id": winner.racer_id,
            "effect_id": 302,
            "message": "The Phoenix Flask ignited.",
        }
    )
    spotlight = {
        "bet_count": 2,
        "player_count": 2,
        "highest_gain": None,
        "highest_loss": None,
        "host_focus": "none",
    }
    records = [
        {
            "metric": "fastest_finish",
            "label": "Fastest official finish",
            "description": "Shortest time.",
            "value": 6_500,
            "display_value": "6.5 seconds",
            "racer_id": winner.racer_id,
            "racer_name": winner.racer.name,
            "racer_slug": winner.racer.slug,
            "sprite_key": winner.racer.sprite_key,
            "color": winner.racer.color,
            "round_number": race.round.number,
            "previous_racer_name": None,
            "previous_display_value": None,
        },
        {
            "metric": "most_falls",
            "label": "Most falls in one race",
            "description": "Most transitions into fallen.",
            "value": 3,
            "display_value": "3 falls",
            "racer_id": record_rival.racer_id,
            "racer_name": record_rival.racer.name,
            "racer_slug": record_rival.racer.slug,
            "sprite_key": record_rival.racer.sprite_key,
            "color": record_rival.racer.color,
            "round_number": race.round.number,
            "previous_racer_name": None,
            "previous_display_value": None,
        },
    ]

    montage = build_replay_montage(
        race,
        betting_spotlight=spotlight,
        new_world_records=records,
    )
    kinds = [stage["kind"] for stage in montage["stages"]]

    assert "betting_spotlight" in kinds
    assert kinds.count("world_record_celebration") == 4
    assert kinds[-5:] == [
        "interview_question",
        "interview_answer",
        "potion_callout",
        "potion_response",
        "outro",
    ]
    assert montage["winner_potion"]["item_name"] == "Phoenix Flask"
    record_stages = [
        stage
        for stage in montage["stages"]
        if stage["kind"] == "world_record_celebration"
    ]
    assert [stage["record_beat"] for stage in record_stages] == [
        "intro",
        "shoutout",
        "shoutout",
        "finale",
    ]
    assert winner.racer.name in record_stages[1]["caption"]
    assert record_rival.racer.name in record_stages[2]["caption"]
    assert all(
        stage["duration_ms"] >= MIN_INFORMATION_STAGE_MS
        for stage in montage["stages"]
        if stage["kind"] in {"betting_spotlight", "world_record_celebration"}
    )
    assert all(
        stage["duration_ms"] >= commentary_duration_ms(stage["caption"])
        for stage in montage["stages"]
    )
    assert [
        stage["offset_ms"] for stage in montage["stages"]
    ] == sorted(stage["offset_ms"] for stage in montage["stages"])
