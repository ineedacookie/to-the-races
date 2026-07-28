from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from apps.betting.models import Bet
from apps.betting.services import place_bet, settle_round
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.models import (
    Race,
    RaceEntry,
    Racer,
    Round,
    SeatOwnership,
    SpectatorSeatDefinition,
)
from apps.racing.serializers import build_live_state
from apps.racing.stats import (
    player_betting_records,
    racer_performance_record,
    racer_recent_history,
    racer_recent_performance_record,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _settled_round(
    *,
    number: int,
    entries: list[tuple[Racer, int | None, str]],
) -> Round:
    now = timezone.now()
    current_round = Round.objects.create(
        number=number,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=5),
        locks_at=now - timedelta(minutes=4),
        race_starts_at=now - timedelta(minutes=3),
        race_ends_at=now - timedelta(minutes=2),
        results_end_at=now - timedelta(minutes=1),
        settled_at=now,
    )
    race = Race.objects.create(round=current_round, completed_at=now)
    for lane, (racer, finish_place, dnf_reason) in enumerate(entries, start=1):
        RaceEntry.objects.create(
            race=race,
            racer=racer,
            lane=lane,
            odds=Decimal("4.00"),
            finish_place=finish_place,
            dnf_reason=dnf_reason,
        )
    return current_round


def test_player_betting_record_derives_from_settled_bets() -> None:
    racer = Racer.objects.create(name="Ace", slug="ace", sprite_key="ace")
    current_round = _settled_round(number=1, entries=[(racer, 1, "")])
    entry = current_round.race.entries.get()
    player = create_player(Device.objects.create(), "Ledger Fan")
    Bet.objects.create(
        player=player,
        round=current_round,
        race_entry=entry,
        amount_cents=500,
        decimal_odds=Decimal("3.00"),
        status=Bet.Status.WON,
        payout_cents=1_650,
        settled_at=timezone.now(),
    )
    Bet.objects.create(
        player=player,
        round=current_round,
        race_entry=entry,
        amount_cents=200,
        decimal_odds=Decimal("3.00"),
        status=Bet.Status.LOST,
        payout_cents=0,
        settled_at=timezone.now(),
    )

    record = player_betting_records(player_ids=[player.pk])[player.pk]

    assert record.winning_bets == 1
    assert record.losing_bets == 1
    assert record.total_staked_cents == 700
    assert record.total_returned_cents == 1_650
    assert record.net_cents == 950


def test_live_state_keeps_complete_player_contract_without_a_round() -> None:
    player = create_player(Device.objects.create(), "Waiting Player")

    live_state = build_live_state(player_id=player.pk)

    assert live_state["round"] is None
    assert live_state["player"]["avatar_recipe"]
    assert live_state["player"]["avatar_version"]
    assert live_state["player"]["avatar_url"].startswith(f"/api/players/{player.pk}/avatar/")
    assert live_state["player"]["bets"] == []
    assert live_state["player"]["item_uses"] == []
    assert live_state["player"]["round_staked_cents"] == 0


def test_player_betting_record_includes_seat_bonus_in_returned_total() -> None:
    racer = Racer.objects.create(name="Throne", slug="throne", sprite_key="throne")
    player = create_player(Device.objects.create(), "Bonus Bettor")
    seat = SpectatorSeatDefinition.objects.create(
        slug="bonus-seat",
        name="Bonus Seat",
        description="Adds profit bonus.",
        price_cents=1_000,
        payout_bonus_bps=2_500,
    )
    current_round = Round.objects.create(
        number=3,
        state=Round.State.OPEN,
        opened_at=timezone.now(),
        locks_at=timezone.now() + timedelta(minutes=1),
        race_starts_at=timezone.now() + timedelta(minutes=2),
        race_ends_at=timezone.now() + timedelta(minutes=3),
        results_end_at=timezone.now() + timedelta(minutes=4),
    )
    race = Race.objects.create(round=current_round)
    live_entry = RaceEntry.objects.create(
        race=race,
        racer=racer,
        lane=1,
        odds=Decimal("2.00"),
    )
    SeatOwnership.objects.create(player=player, seat=seat)
    place_bet(
        player=player,
        race_entry_id=live_entry.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )
    live_entry.finish_place = 1
    live_entry.save(update_fields=["finish_place"])
    current_round.race.completed_at = timezone.now()
    current_round.race.save(update_fields=["completed_at"])
    settle_round(current_round.pk)

    record = player_betting_records(player_ids=[player.pk])[player.pk]

    assert record.total_returned_cents == 1_125
    assert record.net_cents == 625


def test_oops_ledger_ranks_net_betting_losses_not_negative_balances() -> None:
    winner = Racer.objects.create(name="Winner", slug="winner", sprite_key="winner")
    loser = Racer.objects.create(name="Loser", slug="loser", sprite_key="loser")
    rich = create_player(Device.objects.create(), "Rich Player")
    rich.balance_cents = 100
    rich.save(update_fields=["balance_cents", "updated_at"])
    unlucky = create_player(Device.objects.create(), "Unlucky Player")
    round_one = _settled_round(number=10, entries=[(winner, 1, ""), (loser, 2, "")])
    round_two = _settled_round(number=11, entries=[(winner, 1, ""), (loser, 2, "")])
    winner_entry_one = round_one.race.entries.get(racer=winner)
    loser_entry_one = round_one.race.entries.get(racer=loser)
    winner_entry_two = round_two.race.entries.get(racer=winner)
    loser_entry_two = round_two.race.entries.get(racer=loser)
    Bet.objects.create(
        player=unlucky,
        round=round_one,
        race_entry=loser_entry_one,
        amount_cents=1_000,
        decimal_odds=Decimal("4.00"),
        status=Bet.Status.LOST,
        settled_at=timezone.now(),
    )
    Bet.objects.create(
        player=unlucky,
        round=round_two,
        race_entry=loser_entry_two,
        amount_cents=500,
        decimal_odds=Decimal("4.00"),
        status=Bet.Status.LOST,
        settled_at=timezone.now(),
    )
    Bet.objects.create(
        player=rich,
        round=round_one,
        race_entry=winner_entry_one,
        amount_cents=200,
        decimal_odds=Decimal("2.00"),
        status=Bet.Status.WON,
        payout_cents=400,
        settled_at=timezone.now(),
    )
    Bet.objects.create(
        player=rich,
        round=round_two,
        race_entry=winner_entry_two,
        amount_cents=100,
        decimal_odds=Decimal("2.00"),
        status=Bet.Status.LOST,
        settled_at=timezone.now(),
    )

    live_state = build_live_state()
    oops = live_state["debt_board"]

    assert len(oops) == 1
    assert oops[0]["nickname"] == "Unlucky Player"
    assert oops[0]["betting_record"]["net_cents"] == -1_500
    assert rich.pk not in {row["player_id"] for row in oops}


def test_racer_record_counts_dnf_as_loss() -> None:
    racer = Racer.objects.create(name="DNF Racer", slug="dnf-racer", sprite_key="dnf")
    _settled_round(number=20, entries=[(racer, None, "fire_pit")])

    record = racer_performance_record(racer_id=racer.pk)

    assert record.starts == 1
    assert record.wins == 0
    assert record.losses == 1
    assert record.dnfs == 1
    assert record.win_rate == 0.0


def test_recent_racer_form_uses_only_the_latest_fifty_starts() -> None:
    racer = Racer.objects.create(name="Form Racer", slug="form-racer", sprite_key="form")
    for number in range(1, 6):
        _settled_round(number=number, entries=[(racer, 1, "")])
    for number in range(6, 56):
        _settled_round(number=number, entries=[(racer, 2, "")])

    lifetime = racer_performance_record(racer_id=racer.pk)
    recent = racer_recent_performance_record(racer_id=racer.pk)

    assert lifetime.starts == 55
    assert lifetime.wins == 5
    assert recent.starts == 50
    assert recent.wins == 0

    now = timezone.now()
    live_round = Round.objects.create(
        number=56,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(minutes=1),
        race_starts_at=now + timedelta(minutes=2),
        race_ends_at=now + timedelta(minutes=3),
        results_end_at=now + timedelta(minutes=4),
    )
    live_race = Race.objects.create(round=live_round)
    RaceEntry.objects.create(
        race=live_race,
        racer=racer,
        lane=1,
        odds=Decimal("4.00"),
    )

    live_record = build_live_state()["round"]["entries"][0]["record"]

    assert live_record["starts"] == 50
    assert live_record["wins"] == 0


def test_recent_racer_form_counts_each_dnf_reason() -> None:
    racer = Racer.objects.create(name="Hazard Racer", slug="hazard-racer", sprite_key="hazard")
    for number, reason in enumerate(
        ("fire_pit", "stomped", "knocked_out", "finish_countdown"),
        start=1,
    ):
        _settled_round(number=number, entries=[(racer, None, reason)])
    _settled_round(number=5, entries=[(racer, 1, "")])

    recent = racer_recent_performance_record(racer_id=racer.pk)

    assert recent.starts == 5
    assert recent.finishes == 1
    assert recent.dnfs == 4
    assert recent.dnf_reason_count("fire_pit") == 1
    assert recent.dnf_reason_count("stomped") == 1
    assert recent.dnf_reason_count("knocked_out") == 1
    assert recent.dnf_reason_count("finish_countdown") == 1


def test_racer_recent_history_includes_round_lane_odds_and_outcome() -> None:
    racer = Racer.objects.create(name="History", slug="history", sprite_key="history")
    current_round = _settled_round(number=42, entries=[(racer, 2, "")])
    entry = current_round.race.entries.get()
    entry.odds = Decimal("5.25")
    entry.lane = 3
    entry.save(update_fields=["odds", "lane"])

    history = racer_recent_history(racer_id=racer.pk)

    assert len(history) == 1
    assert history[0].round_number == 42
    assert history[0].lane == 3
    assert history[0].odds == "5.25"
    assert history[0].finish_place == 2


def test_live_state_exposes_player_and_racer_records() -> None:
    racer = Racer.objects.create(name="Card", slug="card", sprite_key="card")
    player = create_player(Device.objects.create(), "State Reader")
    current_round = Round.objects.create(
        number=99,
        state=Round.State.OPEN,
        opened_at=timezone.now(),
        locks_at=timezone.now() + timedelta(minutes=1),
        race_starts_at=timezone.now() + timedelta(minutes=2),
        race_ends_at=timezone.now() + timedelta(minutes=3),
        results_end_at=timezone.now() + timedelta(minutes=4),
    )
    race = Race.objects.create(round=current_round)
    RaceEntry.objects.create(
        race=race,
        racer=racer,
        lane=1,
        odds=Decimal("3.50"),
    )
    _settled_round(number=98, entries=[(racer, 1, "")])

    live_state = build_live_state(player_id=player.pk)

    assert live_state["protocol_version"] == 14
    assert live_state["player"]["betting_record"]["total_bets"] == 0
    assert live_state["round"]["entries"][0]["record"]["starts"] == 1
    assert live_state["round"]["entries"][0]["record"]["wins"] == 1


def test_identity_crisis_official_finish_place_counts_as_win() -> None:
    body = Racer.objects.create(name="Body", slug="body", sprite_key="body")
    identity = Racer.objects.create(name="Identity", slug="identity", sprite_key="identity")
    now = timezone.now()
    current_round = Round.objects.create(
        number=77,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=5),
        locks_at=now - timedelta(minutes=4),
        race_starts_at=now - timedelta(minutes=3),
        race_ends_at=now - timedelta(minutes=2),
        results_end_at=now - timedelta(minutes=1),
        settled_at=now,
    )
    race = Race.objects.create(round=current_round, completed_at=now)
    RaceEntry.objects.create(
        race=race,
        racer=body,
        lane=1,
        odds=Decimal("3.00"),
        finish_place=None,
        dnf_reason="identity_stolen",
    )
    RaceEntry.objects.create(
        race=race,
        racer=identity,
        lane=2,
        odds=Decimal("3.00"),
        finish_place=1,
    )

    body_record = racer_performance_record(racer_id=body.pk)
    identity_record = racer_performance_record(racer_id=identity.pk)

    assert body_record.wins == 0
    assert body_record.losses == 1
    assert identity_record.wins == 1
    assert identity_record.losses == 0
