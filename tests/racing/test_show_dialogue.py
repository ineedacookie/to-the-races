from __future__ import annotations

from apps.racing.show_dialogue import (
    host_clip_reaction,
    host_intro,
    host_outro,
    serialize_dialogue,
    winner_interview_answer,
    winner_interview_question,
    winner_potion_response,
)


def _racer(
    racer_id: int,
    name: str,
    sprite_key: str,
) -> dict[str, object]:
    return {
        "racer_id": racer_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "sprite_key": sprite_key,
        "color": "#ffffff",
        "finish_place": 1,
        "dnf_reason": "",
    }


def test_dialogue_is_deterministic_but_varies_across_playback_keys() -> None:
    first = host_intro("round-one", clip_count=3, beat=1)
    repeated = host_intro("round-one", clip_count=3, beat=1)
    variants = {
        host_intro(f"round-{index}", clip_count=3, beat=1).caption
        for index in range(12)
    }

    assert first == repeated
    assert len(variants) > 1
    assert first.speaker_name == "Chip McChatter"
    assert first.speaker_kind == "host"


def test_outro_uses_a_short_title_without_timing_instructions() -> None:
    outro = host_outro("round-one", "Bonejamin")

    assert len(outro.detail) <= 50
    assert outro.detail
    assert "show ends" not in outro.detail.lower()


def test_racer_answers_use_personality_slots_and_speaker_metadata() -> None:
    skeleton = _racer(1, "Bonejamin", "skeleton")
    goblin = _racer(2, "Gob Smack", "goblin")
    skeleton_theme, _question = winner_interview_question(
        "round-one",
        skeleton,
    )
    goblin_theme, _question = winner_interview_question(
        "round-one",
        goblin,
    )
    skeleton_answer = winner_interview_answer(
        "round-one",
        skeleton,
        question_kind=skeleton_theme,
    )
    goblin_answer = winner_interview_answer(
        "round-one",
        goblin,
        question_kind=goblin_theme,
    )

    assert skeleton_answer.caption != goblin_answer.caption
    assert any(
        word in skeleton_answer.caption.lower()
        for word in ("bone", "rib", "rattle", "skull", "marrow")
    )
    assert any(
        word in goblin_answer.caption.lower()
        for word in (
            "goblin",
            "exploit",
            "rulebook",
            "yelled",
            "speedran",
            "oi",
            "invoice",
            "bad decision",
        )
    )
    serialized = serialize_dialogue(skeleton_answer)
    assert serialized["speaker"] == {
        "kind": "racer",
        "name": "Bonejamin",
        "racer_id": 1,
        "sprite_key": "skeleton",
    }


def test_all_racer_voices_and_interview_paths_produce_complete_dialogue() -> None:
    sprite_keys = (
        "skeleton",
        "mushroom",
        "goblin",
        "flying-eye",
        "mimic",
        "rat",
        "slime",
        "bat",
    )
    for racer_id, sprite_key in enumerate(sprite_keys, start=1):
        racer = _racer(racer_id, f"Racer {racer_id}", sprite_key)
        for question_kind in ("strategy", "chaos", "legacy", "rivals"):
            answer = winner_interview_answer(
                "voice-audit",
                racer,
                question_kind=question_kind,
            )
            assert answer.caption.strip()
            assert answer.speaker_kind == "racer"
            assert answer.racer_id == racer_id

        potion_answer = winner_potion_response(
            "voice-audit",
            racer,
            {
                "effect_id": 99,
                "item_name": "Mystery Tonic",
                "buyer": "A Spectator",
            },
        )
        assert "Mystery Tonic" in potion_answer.detail
        assert potion_answer.caption.strip()


def test_highlight_reactions_cover_specific_and_fallback_event_kinds() -> None:
    for event_kind in (
        "finish",
        "destroyed",
        "knockout",
        "pileup",
        "obstacle_hit",
        "portal_hop",
        "wrong_way",
        "showboat",
        "stumble",
        "body_check",
    ):
        beat = host_clip_reaction(
            "reaction-audit",
            clip_id=f"clip-{event_kind}",
            clip_kind="incident",
            event_kind=event_kind,
            racer_names=("Bonejamin",),
            source_caption="The race event happened.",
        )
        assert beat.caption.strip()
        assert beat.detail == "The race event happened."
        assert beat.speaker_kind == "host"
