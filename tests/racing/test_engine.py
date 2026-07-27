from __future__ import annotations

from apps.racing.sim.engine import simulate_race
from apps.racing.sim.profiles import derive_fixed_odds, estimate_outcomes
from apps.racing.sim.types import RaceEffect, RacerProfile, SimulationConfig
from hypothesis import given, settings
from hypothesis import strategies as st


def profiles() -> list[RacerProfile]:
    return [
        RacerProfile(
            racer_id=index,
            name=f"Racer {index}",
            sprite_key=f"racer-{index}",
            color="#ffffff",
            base_speed=0.82 + index * 0.07,
            resilience=0.25 + index * 0.08,
            recovery=0.75 - index * 0.05,
            aggression=0.20 + index * 0.11,
            chaos=0.35 + index * 0.09,
        )
        for index in range(1, 7)
    ]


def hazard_profiles() -> list[RacerProfile]:
    return [
        RacerProfile(
            racer_id=index,
            name=f"Hazard Racer {index}",
            sprite_key=f"hazard-racer-{index}",
            color="#ffffff",
            base_speed=1.0,
            resilience=0.6,
            recovery=0.3,
            aggression=0.8,
            chaos=0.9,
        )
        for index in range(1, 5)
    ]


def test_same_seed_produces_identical_timeline_and_result() -> None:
    first = simulate_race(profiles(), seed=847_221)
    second = simulate_race(profiles(), seed=847_221)

    assert first == second


def test_default_pace_is_fifty_percent_faster_and_finishes_in_about_twenty_seconds() -> None:
    config = SimulationConfig(chaos_scale=0, knockout_scale=0)
    assert config.base_track_speed == 0.045

    result = simulate_race(
        profiles(),
        seed=1,
        config=config,
    )

    duration_seconds = result.duration_ticks / result.tick_rate
    assert 21 <= duration_seconds <= 24
    assert len(result.finish_order) == len(profiles())


def test_frames_stay_in_bounds_and_placements_are_unique() -> None:
    result = simulate_race(profiles(), seed=92)

    for frame in result.timeline:
        assert 0 <= frame["tick"] <= result.duration_ticks
        for racer in frame["racers"]:
            assert 0.0 <= racer["x"] <= 0.945
            assert 0.0 <= racer["y"] <= 1.0

    places = [
        racer["place"]
        for racer in result.timeline[-1]["racers"]
        if racer["place"] is not None
    ]
    assert sorted(places) == list(range(1, len(places) + 1))
    assert len(set(result.finish_order)) == len(result.finish_order)


def test_safety_limit_destroys_remaining_racers_instead_of_timing_out() -> None:
    result = simulate_race(
        profiles(),
        seed=1,
        config=SimulationConfig(duration_seconds=1),
    )

    assert result.finish_order == []
    assert len(result.dnf) == 6
    assert {item["reason"] for item in result.dnf} == {"track_consumed"}
    assert all(racer["state"] == "destroyed" for racer in result.timeline[-1]["racers"])
    assert not any(event["kind"] == "timeout" for event in result.events)


def test_first_finisher_starts_thirty_second_elimination_clock() -> None:
    racers = [
        RacerProfile(
            racer_id=1,
            name="Quick",
            sprite_key="quick",
            color="#ffffff",
            base_speed=2.0,
            resilience=1.0,
            recovery=0.5,
            aggression=0.0,
            chaos=0.0,
        ),
        RacerProfile(
            racer_id=2,
            name="Unhurried",
            sprite_key="unhurried",
            color="#ffffff",
            base_speed=0.01,
            resilience=1.0,
            recovery=0.5,
            aggression=0.0,
            chaos=0.0,
        ),
    ]

    result = simulate_race(
        racers,
        seed=14,
        config=SimulationConfig(
            duration_seconds=5,
            finish_x=0.1,
            chaos_scale=0,
            action_scale=0,
            knockout_scale=0,
        ),
    )

    first_finish_tick = result.finish_ticks[1]
    expected_deadline = first_finish_tick + 30 * result.tick_rate
    assert result.finish_order == [1]
    assert result.finish_deadline_tick == expected_deadline
    assert result.duration_ticks == expected_deadline
    assert result.dnf == [{"racer_id": 2, "reason": "finish_countdown"}]
    assert any(
        event["kind"] == "timeout"
        and event["racer_id"] == 2
        and event["tick"] == expected_deadline
        for event in result.events
    )
    assert next(
        racer for racer in result.timeline[-1]["racers"] if racer["id"] == 2
    )["state"] == "dnf"


def test_fallen_racer_crawls_at_half_speed_until_recovery() -> None:
    racers = [
        RacerProfile(
            racer_id=index,
            name=f"Crawler {index}",
            sprite_key=f"crawler-{index}",
            color="#ffffff",
            base_speed=1.0,
            resilience=1.0,
            recovery=0.0,
            aggression=0.0,
            chaos=0.0,
        )
        for index in (1, 2)
    ]
    result = simulate_race(
        racers,
        seed=42,
        config=SimulationConfig(
            duration_seconds=5,
            chaos_scale=0,
            knockout_scale=0,
        ),
        effects=[RaceEffect(kind="trip_tonic", strength=0.8, racer_id=1)],
    )

    for current, following in zip(result.timeline, result.timeline[1:], strict=False):
        crawler_now = next(racer for racer in current["racers"] if racer["id"] == 1)
        crawler_next = next(racer for racer in following["racers"] if racer["id"] == 1)
        runner_now = next(racer for racer in current["racers"] if racer["id"] == 2)
        runner_next = next(racer for racer in following["racers"] if racer["id"] == 2)
        if crawler_now["state"] == crawler_next["state"] == "fallen":
            crawl_distance = crawler_next["x"] - crawler_now["x"]
            run_distance = runner_next["x"] - runner_now["x"]
            assert 0 < crawl_distance < run_distance * 0.65
            break
    else:
        raise AssertionError("Expected consecutive crawl frames.")


def test_outer_lane_wander_can_destroy_racer_in_fire_pit() -> None:
    result = simulate_race(
        hazard_profiles(),
        seed=0,
        config=SimulationConfig(
            duration_seconds=12,
            chaos_scale=8,
            action_scale=0,
            knockout_scale=0,
        ),
    )

    assert {"racer_id": 1, "reason": "fire_pit"} in result.dnf
    assert any(
        event["kind"] == "destroyed" and "fire pit" in event["message"]
        for event in result.events
    )


def test_stomping_fallen_racer_destroys_them() -> None:
    result = simulate_race(
        hazard_profiles(),
        seed=8,
        config=SimulationConfig(
            duration_seconds=12,
            chaos_scale=8,
            action_scale=0,
            knockout_scale=0,
        ),
    )

    assert {"racer_id": 4, "reason": "stomped"} in result.dnf
    assert any(
        event["kind"] == "destroyed" and "stomped" in event["message"]
        for event in result.events
    )


def test_odds_are_derived_for_every_racer() -> None:
    racers = profiles()
    odds = derive_fixed_odds(racers)

    assert odds.keys() == {racer.racer_id for racer in racers}
    assert all(value >= 1.25 for value in odds.values())
    assert all(value.as_tuple().exponent == -2 for value in odds.values())


def test_odds_price_the_outer_lanes_fire_pit_risk() -> None:
    evenly_matched = [
        RacerProfile(
            racer_id=index,
            name=f"Even Racer {index}",
            sprite_key=f"even-racer-{index}",
            color="#ffffff",
            base_speed=1.0,
            resilience=0.5,
            recovery=0.5,
            aggression=0.5,
            chaos=0.7,
        )
        for index in range(1, 5)
    ]

    estimate = estimate_outcomes(evenly_matched)
    odds = derive_fixed_odds(evenly_matched)

    assert estimate.fire_pit_probabilities[1] > 0.35
    assert estimate.fire_pit_probabilities[4] > 0.35
    assert estimate.fire_pit_probabilities[2] == 0
    assert estimate.fire_pit_probabilities[3] == 0
    assert estimate.dnf_probabilities[1] > estimate.dnf_probabilities[2]
    assert estimate.dnf_probabilities[4] > estimate.dnf_probabilities[3]
    assert odds[1] > odds[2]
    assert odds[4] > odds[3]


def test_odds_sampling_is_deterministic() -> None:
    racers = profiles()[:4]

    first = derive_fixed_odds(racers)
    second = derive_fixed_odds(racers)

    assert first == second


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_seeded_races_preserve_bounds_and_crossing_order(seed: int) -> None:
    result = simulate_race(profiles(), seed=seed)

    assert all(
        0.0 <= racer["x"] <= 0.945 and 0.0 <= racer["y"] <= 1.0
        for frame in result.timeline
        for racer in frame["racers"]
    )
    crossing_ticks = [result.finish_ticks[racer_id] for racer_id in result.finish_order]
    assert crossing_ticks == sorted(crossing_ticks)
