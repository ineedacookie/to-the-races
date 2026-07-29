from __future__ import annotations

import math
import re
from typing import Any

from apps.racing.models import Race
from apps.racing.show_dialogue import (
    DialogueBeat,
    host_betting_spotlight,
    host_clip_reaction,
    host_intro,
    host_outro,
    host_podium,
    host_potion_callout,
    host_record_finale,
    host_record_intro,
    host_record_shoutout,
    serialize_dialogue,
    winner_interview_answer,
    winner_interview_question,
    winner_potion_response,
)

MONTAGE_VERSION = 2
REPLAY_PROMPT_SECONDS = 5
DISPLAY_EPILOG_SECONDS = 9
MAX_INCIDENT_CLIPS = 2
MIN_CLIPS = 2
MAX_CLIPS = 3
PLAYBACK_RATE = 0.5
CLIP_TRANSITION_MS = 350
MAX_FRAMES_PER_CLIP = 32
WORDS_PER_MINUTE = 200
READING_BUFFER_MS = 2_400
MIN_SPOKEN_STAGE_MS = 6_000
MIN_INFORMATION_STAGE_MS = 6_500
RECORD_FINALE_MS = 7_000

EVENT_WEIGHTS: dict[str, int] = {
    "destroyed": 110,
    "knockout": 105,
    "pileup": 95,
    "obstacle_hit": 90,
    "body_check": 80,
    "portal_hop": 75,
    "timeout": 70,
    "wrong_way": 55,
    "showboat": 50,
    "evasive_juke": 45,
    "panic_sprint": 45,
    "stumble": 40,
    "recover": 35,
    "lane_drift": 25,
    "turn_around": 20,
}
PRIVATE_EVENT_KINDS = {"potion_used", "potion_triggered", "potion_fizzled"}
TONIC_KINDS = {
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
BENEFICIAL_TONIC_KINDS = {
    "speed_tonic",
    "guard_tonic",
    "growth_tonic",
    "fireproof_tonic",
    "nitro_serum",
    "recovery_brew",
    "ghost_draught",
    "second_wind",
    "phoenix_flask",
}
ONE_SHOT_TRACK_KINDS = {
    "boxing_glove",
    "stop_sign",
    "magnet_mine",
    "portal_gate",
}
TRACK_CONSUMING_EVENT_KINDS = {"obstacle_removed", "item_cleared", "destroyed"}


def _effect_id(effect: dict[str, Any]) -> int | None:
    value = effect.get("id")
    return value if isinstance(value, int) else None


def _effect_kind(effect: dict[str, Any]) -> str:
    value = effect.get("kind")
    return value if isinstance(value, str) else ""


def _public_event(
    event: dict[str, Any],
    effects_by_id: dict[int, dict[str, Any]],
) -> bool:
    kind = event.get("kind")
    if not isinstance(kind, str) or kind in PRIVATE_EVENT_KINDS:
        return False
    effect_id = event.get("effect_id")
    effect = effects_by_id.get(effect_id) if isinstance(effect_id, int) else None
    return effect is None or _effect_kind(effect) not in TONIC_KINDS


def _event_score(
    event: dict[str, Any],
    effects_by_id: dict[int, dict[str, Any]],
) -> int:
    kind = event.get("kind")
    if not isinstance(kind, str):
        return -1
    score = EVENT_WEIGHTS.get(kind, -1)
    if score < 0:
        return score
    effect_id = event.get("effect_id")
    effect = effects_by_id.get(effect_id) if isinstance(effect_id, int) else None
    if effect is not None and _effect_kind(effect) not in TONIC_KINDS:
        score += 18
    if isinstance(event.get("target_id"), int):
        score += 12
    return score


def _event_tick(event: dict[str, Any]) -> int:
    tick = event.get("tick")
    return tick if isinstance(tick, int) else 0


def _timeline_window(
    timeline: list[dict[str, Any]],
    start_tick: int,
    end_tick: int,
) -> list[dict[str, Any]]:
    if not timeline:
        return []
    before = [frame for frame in timeline if int(frame.get("tick", 0)) <= start_tick]
    after = [frame for frame in timeline if int(frame.get("tick", 0)) >= end_tick]
    selected = [
        frame
        for frame in timeline
        if start_tick <= int(frame.get("tick", 0)) <= end_tick
    ]
    if before and (not selected or selected[0] is not before[-1]):
        selected.insert(0, before[-1])
    if after and (not selected or selected[-1] is not after[0]):
        selected.append(after[0])
    if not selected:
        selected = [min(timeline, key=lambda frame: abs(int(frame.get("tick", 0)) - start_tick))]
    if len(selected) <= MAX_FRAMES_PER_CLIP:
        return selected
    last_index = len(selected) - 1
    indices = {
        round(index * last_index / (MAX_FRAMES_PER_CLIP - 1))
        for index in range(MAX_FRAMES_PER_CLIP)
    }
    return [selected[index] for index in sorted(indices)]


def _focus_racer_ids(event: dict[str, Any] | None) -> list[int]:
    if event is None:
        return []
    focus: list[int] = []
    for key in ("racer_id", "target_id"):
        value = event.get(key)
        if isinstance(value, int) and value not in focus:
            focus.append(value)
    return focus


def _leading_racer_ids(timeline: list[dict[str, Any]], anchor_tick: int) -> list[int]:
    if not timeline:
        return []
    frame = min(timeline, key=lambda item: abs(int(item.get("tick", 0)) - anchor_tick))
    racers = frame.get("racers")
    if not isinstance(racers, list):
        return []
    positioned = [
        racer
        for racer in racers
        if isinstance(racer, dict)
        and isinstance(racer.get("id"), int)
        and isinstance(racer.get("x"), (int, float))
    ]
    positioned.sort(key=lambda racer: float(racer["x"]), reverse=True)
    return [int(racer["id"]) for racer in positioned[:2]]


def _consumed_effect_ids(
    events: list[dict[str, Any]],
    effects_by_id: dict[int, dict[str, Any]],
    before_tick: int,
) -> list[int]:
    consumed: set[int] = set()
    for event in events:
        if _event_tick(event) >= before_tick:
            break
        effect_id = event.get("effect_id")
        if not isinstance(effect_id, int):
            continue
        effect = effects_by_id.get(effect_id)
        if effect is None or _effect_kind(effect) in TONIC_KINDS:
            continue
        kind = event.get("kind")
        if kind in TRACK_CONSUMING_EVENT_KINDS or (
            kind == "obstacle_hit" and _effect_kind(effect) in ONE_SHOT_TRACK_KINDS
        ):
            consumed.add(effect_id)
    return sorted(consumed)


def _clip(
    *,
    clip_id: str,
    clip_kind: str,
    anchor_tick: int,
    duration_ticks: int,
    tick_rate: int,
    timeline: list[dict[str, Any]],
    events: list[dict[str, Any]],
    effects_by_id: dict[int, dict[str, Any]],
    event: dict[str, Any] | None,
    caption: str,
) -> dict[str, Any]:
    lead_seconds = 1.5 if clip_kind == "finish" else 1.25
    tail_seconds = 0.75 if clip_kind == "finish" else 0.65
    start_tick = max(0, anchor_tick - round(tick_rate * lead_seconds))
    end_tick = min(duration_ticks, anchor_tick + round(tick_rate * tail_seconds))
    if end_tick <= start_tick:
        end_tick = min(duration_ticks, start_tick + max(tick_rate, 1))
    public_events = [
        item
        for item in events
        if start_tick <= _event_tick(item) <= end_tick
        and _public_event(item, effects_by_id)
    ]
    focus_racer_ids = _focus_racer_ids(event)
    if not focus_racer_ids:
        focus_racer_ids = _leading_racer_ids(timeline, anchor_tick)
    event_kind = event.get("kind") if event is not None else None
    effect_id = event.get("effect_id") if event is not None else None
    clip: dict[str, Any] = {
        "id": clip_id,
        "kind": clip_kind,
        "anchor_tick": anchor_tick,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "playback_rate": PLAYBACK_RATE,
        "caption": caption,
        "focus_racer_ids": focus_racer_ids,
        "event_kind": event_kind if isinstance(event_kind, str) else None,
        "effect_id": effect_id if isinstance(effect_id, int) else None,
        "consumed_effect_ids_at_start": _consumed_effect_ids(
            events,
            effects_by_id,
            start_tick,
        ),
        "timeline": _timeline_window(timeline, start_tick, end_tick),
        "events": public_events,
    }
    return clip


def _finish_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    finishers = [
        event
        for event in events
        if event.get("kind") == "finish" and event.get("finish_place") == 1
    ]
    if finishers:
        return min(finishers, key=_event_tick)
    return next((event for event in events if event.get("kind") == "finish"), None)


def _incident_events(
    events: list[dict[str, Any]],
    effects_by_id: dict[int, dict[str, Any]],
    finish_tick: int | None,
    tick_rate: int,
) -> list[dict[str, Any]]:
    candidates = [
        event
        for event in events
        if event.get("kind") != "finish"
        and _public_event(event, effects_by_id)
        and _event_score(event, effects_by_id) >= 0
    ]
    candidates.sort(
        key=lambda event: (
            -_event_score(event, effects_by_id),
            _event_tick(event),
            str(event.get("kind", "")),
            int(event.get("racer_id", 0)),
        )
    )
    selected: list[dict[str, Any]] = []
    minimum_gap = tick_rate * 2
    for event in candidates:
        tick = _event_tick(event)
        if finish_tick is not None and abs(tick - finish_tick) < minimum_gap:
            continue
        if any(abs(tick - _event_tick(chosen)) < minimum_gap for chosen in selected):
            continue
        selected.append(event)
        if len(selected) >= MAX_INCIDENT_CLIPS:
            break
    selected.sort(key=_event_tick)
    return selected


def _synthetic_clip_anchor(
    duration_ticks: int,
    occupied_ticks: list[int],
    tick_rate: int,
) -> int:
    candidates = [duration_ticks // 3, duration_ticks // 2, (duration_ticks * 2) // 3]
    minimum_gap = tick_rate * 2
    return next(
        (
            tick
            for tick in candidates
            if all(abs(tick - occupied) >= minimum_gap for occupied in occupied_ticks)
        ),
        duration_ticks // 2,
    )


def _clip_visual_duration_ms(clip: dict[str, Any], tick_rate: int) -> int:
    ticks = max(int(clip["end_tick"]) - int(clip["start_tick"]), 1)
    rate = float(clip["playback_rate"])
    return round((ticks / tick_rate / rate) * 1_000)


def commentary_duration_ms(
    caption: str,
    *,
    minimum_ms: int = MIN_SPOKEN_STAGE_MS,
) -> int:
    words = re.findall(r"\b[\w’'-]+\b", caption)
    reading_ms = math.ceil((len(words) / WORDS_PER_MINUTE) * 60_000)
    return max(reading_ms + READING_BUFFER_MS, minimum_ms)


def _entry_payload(entry: Any) -> dict[str, Any]:
    return {
        "racer_id": entry.racer_id,
        "name": entry.racer.name,
        "slug": entry.racer.slug,
        "sprite_key": entry.racer.sprite_key,
        "color": entry.racer.color,
        "finish_place": entry.finish_place,
        "dnf_reason": entry.dnf_reason,
    }


def _winner_payload(race: Race) -> dict[str, Any] | None:
    winner = (
        race.entries.select_related("racer")
        .filter(finish_place=1)
        .order_by("pk")
        .first()
    )
    return _entry_payload(winner) if winner is not None else None


def _winner_potion(
    *,
    winner: dict[str, Any] | None,
    effects: list[dict[str, Any]],
    successful_effect_ids: list[int],
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if winner is None:
        return None
    successful = set(successful_effect_ids)
    priorities = {
        "phoenix_flask": 100,
        "second_wind": 95,
        "nitro_serum": 90,
        "ghost_draught": 85,
        "recovery_brew": 80,
        "fireproof_tonic": 75,
        "guard_tonic": 70,
        "growth_tonic": 65,
        "speed_tonic": 60,
    }
    eligible = [
        effect
        for effect in effects
        if _effect_id(effect) in successful
        and _effect_kind(effect) in BENEFICIAL_TONIC_KINDS
        and effect.get("target_racer_id") == winner["racer_id"]
    ]
    if not eligible:
        return None
    selected = max(
        eligible,
        key=lambda effect: (
            priorities.get(_effect_kind(effect), 0),
            -int(effect.get("activation_tick", 0)),
            -int(_effect_id(effect) or 0),
        ),
    )
    effect_id = _effect_id(selected)
    trigger = next(
        (
            event
            for event in events
            if event.get("effect_id") == effect_id
            and event.get("kind") in {"potion_triggered", "second_wind", "recover"}
        ),
        None,
    )
    return {
        "effect_id": effect_id,
        "kind": _effect_kind(selected),
        "item_name": selected.get("item_name", "mysterious potion"),
        "item_icon": selected.get("item_icon", "✦"),
        "item_color": selected.get("item_color", "#f3bc3e"),
        "buyer": selected.get("buyer", "an anonymous benefactor"),
        "activation_tick": selected.get("activation_tick"),
        "trigger_event_kind": trigger.get("kind") if trigger is not None else None,
        "trigger_tick": trigger.get("tick") if trigger is not None else None,
        "successful": True,
    }


def _stage(
    *,
    stage_id: str,
    kind: str,
    beat: DialogueBeat,
    minimum_ms: int = MIN_SPOKEN_STAGE_MS,
    visual_duration_ms: int = 0,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    duration_ms = max(
        commentary_duration_ms(beat.caption, minimum_ms=minimum_ms),
        visual_duration_ms,
    )
    stage = {
        "id": stage_id,
        "kind": kind,
        "duration_ms": duration_ms,
        "visual_duration_ms": visual_duration_ms,
        **serialize_dialogue(beat),
    }
    if payload is not None:
        stage.update(payload)
    return stage


def _with_offsets(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    offset_ms = 0
    for stage in stages:
        stage["offset_ms"] = offset_ms
        offset_ms += int(stage["duration_ms"])
    return stages


def _show_stages(
    *,
    race: Race,
    playback_key: str,
    clips: list[dict[str, Any]],
    effects: list[dict[str, Any]],
    successful_effect_ids: list[int],
    betting_spotlight: dict[str, Any] | None,
    new_world_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    entries = list(race.entries.select_related("racer").order_by("lane"))
    entry_payloads = [_entry_payload(entry) for entry in entries]
    entries_by_racer = {entry["racer_id"]: entry for entry in entry_payloads}
    winner = _winner_payload(race)
    stages: list[dict[str, Any]] = [
        _stage(
            stage_id="intro-1",
            kind="intro",
            beat=host_intro(playback_key, clip_count=len(clips), beat=1),
        ),
        _stage(
            stage_id="intro-2",
            kind="intro",
            beat=host_intro(playback_key, clip_count=len(clips), beat=2),
        ),
    ]
    for index, clip in enumerate(clips):
        focus_names = [
            entries_by_racer[racer_id]["name"]
            for racer_id in clip["focus_racer_ids"]
            if racer_id in entries_by_racer
        ]
        visual_duration_ms = _clip_visual_duration_ms(clip, race.tick_rate)
        stages.append(
            _stage(
                stage_id=f"replay-{index + 1}",
                kind="clip",
                beat=host_clip_reaction(
                    playback_key,
                    clip_id=str(clip["id"]),
                    clip_kind=str(clip["kind"]),
                    event_kind=clip["event_kind"],
                    racer_names=focus_names,
                    source_caption=str(clip["caption"]),
                ),
                visual_duration_ms=visual_duration_ms + CLIP_TRANSITION_MS,
                payload={
                    "clip_id": clip["id"],
                    "clip_index": index,
                    "clip_count": len(clips),
                },
            )
        )

    if betting_spotlight is not None:
        stages.append(
            _stage(
                stage_id="betting-spotlight",
                kind="betting_spotlight",
                beat=host_betting_spotlight(playback_key, betting_spotlight),
                minimum_ms=MIN_INFORMATION_STAGE_MS,
                payload={"betting_spotlight": betting_spotlight},
            )
        )

    if new_world_records:
        stages.append(
            _stage(
                stage_id="records-intro",
                kind="world_record_celebration",
                beat=host_record_intro(playback_key, len(new_world_records)),
                minimum_ms=MIN_INFORMATION_STAGE_MS,
                payload={"record_beat": "intro", "record_count": len(new_world_records)},
            )
        )
        for index, record in enumerate(new_world_records):
            stages.append(
                _stage(
                    stage_id=f"record-{index + 1}-{record['metric']}",
                    kind="world_record_celebration",
                    beat=host_record_shoutout(
                        playback_key,
                        index=index,
                        record=record,
                    ),
                    minimum_ms=MIN_INFORMATION_STAGE_MS,
                    payload={
                        "record_beat": "shoutout",
                        "record_index": index,
                        "record_count": len(new_world_records),
                        "world_record": record,
                    },
                )
            )
        finale = _stage(
            stage_id="records-finale",
            kind="world_record_celebration",
            beat=host_record_finale(playback_key, len(new_world_records)),
            minimum_ms=RECORD_FINALE_MS,
            payload={"record_beat": "finale", "record_count": len(new_world_records)},
        )
        stages.append(finale)

    stages.append(
        _stage(
            stage_id="podium",
            kind="podium",
            beat=host_podium(playback_key, winner),
            minimum_ms=MIN_INFORMATION_STAGE_MS,
            payload={"winner": winner},
        )
    )
    winner_potion = _winner_potion(
        winner=winner,
        effects=effects,
        successful_effect_ids=successful_effect_ids,
        events=list(race.events or []),
    )
    if winner is not None:
        question_kind, question = winner_interview_question(playback_key, winner)
        stages.append(
            _stage(
                stage_id="interview-question",
                kind="interview_question",
                beat=question,
                payload={"winner": winner, "question_kind": question_kind},
            )
        )
        stages.append(
            _stage(
                stage_id="interview-answer",
                kind="interview_answer",
                beat=winner_interview_answer(
                    playback_key,
                    winner,
                    question_kind=question_kind,
                ),
                payload={"winner": winner, "question_kind": question_kind},
            )
        )
        if winner_potion is not None:
            stages.append(
                _stage(
                    stage_id="potion-callout",
                    kind="potion_callout",
                    beat=host_potion_callout(
                        playback_key,
                        winner,
                        winner_potion,
                    ),
                    payload={"winner": winner, "potion": winner_potion},
                )
            )
            stages.append(
                _stage(
                    stage_id="potion-response",
                    kind="potion_response",
                    beat=winner_potion_response(
                        playback_key,
                        winner,
                        winner_potion,
                    ),
                    payload={"winner": winner, "potion": winner_potion},
                )
            )
    stages.append(
        _stage(
            stage_id="outro",
            kind="outro",
            beat=host_outro(
                playback_key,
                str(winner["name"]) if winner is not None else None,
            ),
        )
    )
    return _with_offsets(stages), winner_potion


def build_replay_montage(
    race: Race,
    *,
    betting_spotlight: dict[str, Any] | None = None,
    new_world_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    timeline = list(race.timeline or [])
    events = list(race.events or [])
    if not timeline or race.duration_ticks <= 0:
        return {}
    inputs = race.inputs or {}
    effects = [
        effect
        for effect in inputs.get("effects", [])
        if isinstance(effect, dict) and _effect_id(effect) is not None
    ]
    effects_by_id = {
        effect_id: effect
        for effect in effects
        if (effect_id := _effect_id(effect)) is not None
    }
    winner_event = _finish_event(events)
    race_result = race.result or {}
    finish_order = race_result.get("finish_order")
    if winner_event is None and isinstance(finish_order, list) and finish_order:
        winner_id = finish_order[0]
        first_finish_tick = race_result.get("first_finish_tick")
        if isinstance(winner_id, int) and isinstance(first_finish_tick, int):
            winner_event = {
                "tick": first_finish_tick,
                "kind": "finish",
                "racer_id": winner_id,
                "finish_place": 1,
                "message": "The winner crossed the line.",
            }
    winner_tick = _event_tick(winner_event) if winner_event is not None else None
    selected_incidents = _incident_events(
        events,
        effects_by_id,
        winner_tick,
        race.tick_rate,
    )

    selections: list[tuple[str, int, dict[str, Any] | None, str]] = []
    for event in selected_incidents:
        message = event.get("message")
        selections.append(
            (
                "incident",
                _event_tick(event),
                event,
                message if isinstance(message, str) else "Trackside chaos erupted.",
            )
        )
    if winner_event is not None:
        message = winner_event.get("message")
        selections.append(
            (
                "finish",
                _event_tick(winner_event),
                winner_event,
                message if isinstance(message, str) else "The winner crossed the line.",
            )
        )
    else:
        final_tick = max((_event_tick(event) for event in events), default=race.duration_ticks)
        selections.append(
            (
                "house_win",
                min(final_tick, race.duration_ticks),
                None,
                "Nobody escaped the chaos. The house wins.",
            )
        )

    while len(selections) < MIN_CLIPS:
        occupied = [selection[1] for selection in selections]
        anchor_tick = _synthetic_clip_anchor(race.duration_ticks, occupied, race.tick_rate)
        selections.insert(
            max(len(selections) - 1, 0),
            (
                "incident",
                anchor_tick,
                None,
                "The field scrambled for position.",
            ),
        )
    selections = selections[-MAX_CLIPS:]

    clips = [
        _clip(
            clip_id=f"clip-{index + 1}",
            clip_kind=clip_kind,
            anchor_tick=anchor_tick,
            duration_ticks=race.duration_ticks,
            tick_rate=race.tick_rate,
            timeline=timeline,
            events=events,
            effects_by_id=effects_by_id,
            event=event,
            caption=caption,
        )
        for index, (clip_kind, anchor_tick, event, caption) in enumerate(selections)
    ]
    generated_at = race.generated_at.isoformat() if race.generated_at is not None else ""
    playback_key = f"{race.round_id}:{race.seed or 0}:{generated_at}"
    successful_effect_ids = [
        effect_id
        for effect_id in inputs.get("successful_effect_ids", [])
        if isinstance(effect_id, int)
    ]
    stages, winner_potion = _show_stages(
        race=race,
        playback_key=playback_key,
        clips=clips,
        effects=effects,
        successful_effect_ids=successful_effect_ids,
        betting_spotlight=betting_spotlight,
        new_world_records=new_world_records or [],
    )
    total_show_ms = sum(int(stage["duration_ms"]) for stage in stages)
    total_playback_ms = sum(
        int(stage["duration_ms"]) for stage in stages if stage["kind"] == "clip"
    )
    return {
        "version": MONTAGE_VERSION,
        "playback_key": playback_key,
        "tick_rate": race.tick_rate,
        "duration_ticks": race.duration_ticks,
        "prompt_seconds": REPLAY_PROMPT_SECONDS,
        "total_playback_ms": total_playback_ms,
        "total_show_ms": total_show_ms,
        "clips": clips,
        "effects": effects,
        "successful_effect_ids": successful_effect_ids,
        "failed_effect_ids": list(inputs.get("failed_effect_ids", [])),
        "stages": stages,
        "betting_spotlight": betting_spotlight,
        "new_world_records": new_world_records or [],
        "winner_potion": winner_potion,
    }


def replay_manifest(montage: dict[str, Any]) -> dict[str, Any]:
    clips = montage.get("clips")
    stages = montage.get("stages")
    if (
        not montage
        or not isinstance(clips, list)
        or not clips
        or not isinstance(stages, list)
        or not stages
    ):
        return {"available": False}
    return {
        "available": True,
        "version": montage.get("version", MONTAGE_VERSION),
        "playback_key": montage.get("playback_key", ""),
        "clip_count": len(clips),
        "prompt_seconds": montage.get("prompt_seconds", REPLAY_PROMPT_SECONDS),
        "total_playback_ms": montage.get("total_playback_ms", 0),
        "total_show_ms": montage.get("total_show_ms", 0),
        "show_started_at": montage.get("show_started_at"),
        "show_ends_at": montage.get("show_ends_at"),
        "stages": [
            {
                key: stage.get(key)
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
            for stage in stages
            if isinstance(stage, dict)
        ],
        "prompt_ends_at": montage.get("prompt_ends_at"),
        "playback_ends_at": montage.get("playback_ends_at"),
        "podium_ends_at": montage.get("podium_ends_at"),
    }
