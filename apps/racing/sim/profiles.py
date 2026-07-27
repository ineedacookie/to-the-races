from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

from apps.racing.sim.engine import simulate_race
from apps.racing.sim.types import RacerProfile, SimulationConfig

ODDS_SIMULATION_TRIALS = 128
ODDS_PRIOR_TRIALS = 8.0
ODDS_RETURN_RATE = 0.88
ODDS_SEED_BASE = 0x0DD5CA1E
ODDS_SEED_STEP = 104_729


@dataclass(frozen=True, slots=True)
class OutcomeEstimate:
    win_probabilities: dict[int, float]
    fire_pit_probabilities: dict[int, float]
    dnf_probabilities: dict[int, float]
    house_win_probability: float


def performance_score(profile: RacerProfile) -> float:
    durability = 0.80 + (profile.resilience * 0.18) + (profile.recovery * 0.15)
    combat = 0.97 + (profile.aggression * 0.05)
    unpredictability = 1.0 - (profile.chaos * 0.08)
    return max(profile.base_speed**2 * durability * combat * unpredictability, 0.01)


@lru_cache(maxsize=32)
def _sample_outcomes(
    profiles: tuple[RacerProfile, ...],
    trials: int,
    config: SimulationConfig,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int]:
    sampling_config = replace(
        config,
        snapshot_every_ticks=config.duration_ticks + config.finish_grace_ticks + 1,
    )
    wins: Counter[int] = Counter()
    fire_pit_dnfs: Counter[int] = Counter()
    all_dnfs: Counter[int] = Counter()
    house_wins = 0
    for trial in range(trials):
        result = simulate_race(
            list(profiles),
            seed=ODDS_SEED_BASE + trial * ODDS_SEED_STEP,
            config=sampling_config,
        )
        if result.finish_order:
            wins[result.finish_order[0]] += 1
        else:
            house_wins += 1
        for dnf in result.dnf:
            racer_id = dnf["racer_id"]
            all_dnfs[racer_id] += 1
            if dnf["reason"] == "fire_pit":
                fire_pit_dnfs[racer_id] += 1
    return (
        tuple(wins[profile.racer_id] for profile in profiles),
        tuple(fire_pit_dnfs[profile.racer_id] for profile in profiles),
        tuple(all_dnfs[profile.racer_id] for profile in profiles),
        house_wins,
    )


def estimate_outcomes(
    profiles: list[RacerProfile],
    *,
    trials: int = ODDS_SIMULATION_TRIALS,
    config: SimulationConfig | None = None,
) -> OutcomeEstimate:
    if not profiles:
        return OutcomeEstimate({}, {}, {}, 0.0)
    if trials <= 0:
        raise ValueError("Odds simulation trials must be positive.")
    racer_ids = [profile.racer_id for profile in profiles]
    if len(set(racer_ids)) != len(racer_ids):
        raise ValueError("Racer IDs must be unique when estimating odds.")

    profile_tuple = tuple(profiles)
    win_counts, fire_pit_counts, dnf_counts, house_wins = _sample_outcomes(
        profile_tuple,
        trials,
        config or SimulationConfig(),
    )
    return OutcomeEstimate(
        win_probabilities={
            profile.racer_id: win_counts[index] / trials
            for index, profile in enumerate(profiles)
        },
        fire_pit_probabilities={
            profile.racer_id: fire_pit_counts[index] / trials
            for index, profile in enumerate(profiles)
        },
        dnf_probabilities={
            profile.racer_id: dnf_counts[index] / trials
            for index, profile in enumerate(profiles)
        },
        house_win_probability=house_wins / trials,
    )


def derive_fixed_odds(
    profiles: list[RacerProfile],
    *,
    trials: int = ODDS_SIMULATION_TRIALS,
    config: SimulationConfig | None = None,
) -> dict[int, Decimal]:
    if not profiles:
        return {}

    estimate = estimate_outcomes(profiles, trials=trials, config=config)
    scores = {profile.racer_id: performance_score(profile) for profile in profiles}
    total_score = sum(scores.values())
    odds: dict[int, Decimal] = {}
    for profile in profiles:
        prior_probability = scores[profile.racer_id] / total_score
        sampled_wins = estimate.win_probabilities[profile.racer_id] * trials
        implied_probability = (
            sampled_wins + prior_probability * ODDS_PRIOR_TRIALS
        ) / (trials + ODDS_PRIOR_TRIALS)
        raw_odds = min(
            max(ODDS_RETURN_RATE / max(implied_probability, 0.001), 1.25),
            12.0,
        )
        five_cent_steps = (Decimal(str(raw_odds)) / Decimal("0.05")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        odds[profile.racer_id] = (five_cent_steps * Decimal("0.05")).quantize(
            Decimal("0.00")
        )
    return odds
