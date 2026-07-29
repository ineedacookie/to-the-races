from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.betting.highlights import (
    round_betting_spotlight,
    serialize_round_betting_spotlight,
)
from apps.betting.models import Bet
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.models import Race, RaceEntry, Racer, Round
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _round_and_entry() -> tuple[Round, RaceEntry]:
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=3),
        locks_at=now - timedelta(minutes=2),
        race_starts_at=now - timedelta(minutes=1),
        race_ends_at=now,
        results_end_at=now + timedelta(seconds=20),
        settled_at=now,
    )
    racer = Racer.objects.create(
        name="Bet Drama Racer",
        slug="bet-drama-racer",
        sprite_key="skeleton",
    )
    race = Race.objects.create(
        round=current_round,
        completed_at=now,
    )
    entry = RaceEntry.objects.create(
        race=race,
        racer=racer,
        lane=1,
        odds=Decimal("2.00"),
        finish_place=1,
        finish_tick=20,
    )
    return current_round, entry


def _settled_bet(
    *,
    current_round: Round,
    entry: RaceEntry,
    player_name: str,
    stake: int,
    payout: int,
) -> None:
    player = create_player(Device.objects.create(), player_name)
    Bet.objects.create(
        player=player,
        round=current_round,
        race_entry=entry,
        amount_cents=stake,
        decimal_odds=Decimal("2.00"),
        status=Bet.Status.WON if payout > 0 else Bet.Status.LOST,
        payout_cents=payout,
        settled_at=timezone.now(),
    )


def test_spotlight_is_omitted_when_the_round_has_no_settled_bets() -> None:
    current_round, entry = _round_and_entry()
    pending_player = create_player(Device.objects.create(), "Pending")
    Bet.objects.create(
        player=pending_player,
        round=current_round,
        race_entry=entry,
        amount_cents=500,
        decimal_odds=Decimal("2.00"),
    )

    assert round_betting_spotlight(current_round, seed="empty") is None


def test_spotlight_handles_one_sided_and_neutral_results() -> None:
    current_round, entry = _round_and_entry()
    _settled_bet(
        current_round=current_round,
        entry=entry,
        player_name="Gainer",
        stake=500,
        payout=1_200,
    )
    _settled_bet(
        current_round=current_round,
        entry=entry,
        player_name="Square",
        stake=500,
        payout=500,
    )

    spotlight = round_betting_spotlight(current_round, seed="one-side")

    assert spotlight is not None
    assert spotlight.highest_gain is not None
    assert spotlight.highest_gain.nickname == "Gainer"
    assert spotlight.highest_gain.net_cents == 700
    assert spotlight.highest_loss is None
    assert spotlight.host_focus in {"gain", "none"}


def test_spotlight_aggregates_both_sides_and_is_deterministic() -> None:
    current_round, entry = _round_and_entry()
    _settled_bet(
        current_round=current_round,
        entry=entry,
        player_name="Big Winner",
        stake=800,
        payout=2_400,
    )
    _settled_bet(
        current_round=current_round,
        entry=entry,
        player_name="Big Loss",
        stake=1_300,
        payout=0,
    )

    first = round_betting_spotlight(current_round, seed="round:99")
    second = round_betting_spotlight(current_round, seed="round:99")

    assert first == second
    assert first is not None
    assert first.highest_gain is not None
    assert first.highest_loss is not None
    assert first.highest_gain.net_cents == 1_600
    assert first.highest_loss.net_cents == -1_300
    payload = serialize_round_betting_spotlight(first)
    assert payload["highest_gain"]["avatar_url"].startswith("/api/players/")
    assert payload["highest_loss"]["nickname"] == "Big Loss"
