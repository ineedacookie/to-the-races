from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps.racing.sim.types import RacerProfile


def performance_score(profile: RacerProfile) -> float:
    durability = 0.80 + (profile.resilience * 0.18) + (profile.recovery * 0.15)
    combat = 0.97 + (profile.aggression * 0.05)
    unpredictability = 1.0 - (profile.chaos * 0.08)
    return max(profile.base_speed**2 * durability * combat * unpredictability, 0.01)


def derive_fixed_odds(profiles: list[RacerProfile]) -> dict[int, Decimal]:
    if not profiles:
        return {}

    scores = {profile.racer_id: performance_score(profile) for profile in profiles}
    total_score = sum(scores.values())
    odds: dict[int, Decimal] = {}
    for profile in profiles:
        implied_probability = scores[profile.racer_id] / total_score
        raw_odds = min(max(0.88 / implied_probability, 1.25), 12.0)
        five_cent_steps = (Decimal(str(raw_odds)) / Decimal("0.05")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        odds[profile.racer_id] = (five_cent_steps * Decimal("0.05")).quantize(
            Decimal("0.00")
        )
    return odds
