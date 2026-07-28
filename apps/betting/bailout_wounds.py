from __future__ import annotations

import hashlib
import random
from typing import TypedDict


class WoundCoordinate(TypedDict):
    x: float
    y: float


MIN_WOUND_COUNT = 2
MAX_WOUND_COUNT = 5
BAILOUT_REWARD_CENTS = 2_000

SAFE_WOUND_SLOTS: tuple[tuple[float, float], ...] = (
    (0.35, 0.42),
    (0.55, 0.38),
    (0.42, 0.58),
    (0.68, 0.52),
    (0.28, 0.55),
    (0.50, 0.70),
    (0.62, 0.45),
    (0.38, 0.75),
)


def _session_seed(*, player_id: int, round_id: int, salt: int) -> int:
    digest = hashlib.sha256(
        f"bailout:{player_id}:{round_id}:{salt}".encode(),
    ).hexdigest()
    return int(digest[:16], 16)


def pick_bailout_race_entry(*, player_id: int, round_id: int, entry_ids: list[int]) -> int:
    if not entry_ids:
        raise ValueError("Cannot pick a bailout racer without entries.")
    rng = random.Random(_session_seed(player_id=player_id, round_id=round_id, salt=0))
    return rng.choice(entry_ids)


def generate_bailout_wounds(
    *,
    player_id: int,
    round_id: int,
    race_entry_id: int,
) -> tuple[int, list[WoundCoordinate]]:
    rng = random.Random(
        _session_seed(player_id=player_id, round_id=round_id, salt=race_entry_id),
    )
    wound_count = rng.randint(MIN_WOUND_COUNT, MAX_WOUND_COUNT)
    slots = rng.sample(SAFE_WOUND_SLOTS, wound_count)
    return wound_count, [{"x": x, "y": y} for x, y in slots]
