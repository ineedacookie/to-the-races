from __future__ import annotations

import re
from dataclasses import dataclass

PROFANITY_BLOCKLIST = frozenset(
    {
        "damn",
        "hell",
        "crap",
        "ass",
        "bastard",
        "bitch",
        "shit",
        "fuck",
    }
)

URL_PATTERN = re.compile(
    r"(https?://|www\.|[a-z0-9-]+\.(com|net|org|io|gg|co|ly|me|tv|dev)\b)",
    re.IGNORECASE,
)
ALLOWED_TEXT = re.compile(r"^[a-zA-Z0-9 .,!?'-]+$")
PRESET_REACTION_TEXT = {
    "cheer": "CHEER!",
    "boo": "BOOO!",
    "cry": "WAAAH!",
}


@dataclass(frozen=True, slots=True)
class AudienceReaction:
    kind: str
    text: str
    racer_id: int | None


class AudienceValidationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def sanitize_reaction_text(raw: object) -> str:
    if not isinstance(raw, str):
        raise AudienceValidationError("Reaction text must be a string.")
    cleaned = "".join(
        character for character in raw if character.isprintable() and character != "\x7f"
    )
    collapsed = " ".join(cleaned.split())
    if not collapsed:
        raise AudienceValidationError("Reaction text cannot be empty.")
    if len(collapsed) > 24:
        raise AudienceValidationError("Reaction text must be 24 characters or fewer.")
    if URL_PATTERN.search(collapsed):
        raise AudienceValidationError("Links are not allowed in reactions.")
    if not ALLOWED_TEXT.fullmatch(collapsed):
        raise AudienceValidationError("Reaction text contains unsupported characters.")
    words = set(re.findall(r"[a-zA-Z]+", collapsed.lower()))
    if words & PROFANITY_BLOCKLIST:
        raise AudienceValidationError("That reaction is not allowed.")
    return collapsed


def parse_audience_reaction(payload: dict[str, object]) -> AudienceReaction:
    kind = payload.get("kind")
    if kind not in {*PRESET_REACTION_TEXT, "shout"}:
        raise AudienceValidationError("Reaction kind must be cheer, boo, cry, or shout.")

    if kind == "shout":
        text = sanitize_reaction_text(payload.get("text", ""))
    else:
        text = PRESET_REACTION_TEXT[str(kind)]

    racer_id: int | None = None
    if "racer_id" in payload and payload["racer_id"] is not None:
        racer_value = payload["racer_id"]
        if not isinstance(racer_value, int):
            try:
                racer_id = int(str(racer_value))
            except (TypeError, ValueError) as error:
                raise AudienceValidationError("Racer id must be an integer.") from error
        else:
            racer_id = racer_value
        if racer_id <= 0:
            raise AudienceValidationError("Racer id must be positive.")

    return AudienceReaction(kind=str(kind), text=text, racer_id=racer_id)
