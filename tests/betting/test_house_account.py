from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.betting.house_account import (
    format_money,
    house_account_summary,
    house_round_history,
    recent_house_transactions,
)
from apps.betting.models import LedgerEntry
from apps.players.models import Device, Player
from apps.players.services import create_player
from apps.racing.models import Race, RaceEntry, Racer, Round
from django.utils import timezone

pytestmark = pytest.mark.django_db


def settled_round(*, number: int, winner: Racer | None) -> Round:
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
    race = Race.objects.create(
        round=current_round,
        completed_at=now,
        result={"house_wins": winner is None},
    )
    if winner is not None:
        RaceEntry.objects.create(
            race=race,
            racer=winner,
            lane=1,
            odds=Decimal("3.00"),
            finish_place=1,
        )
    return current_round


def ledger(
    *,
    player: Player,
    current_round: Round,
    kind: str,
    amount_cents: int,
    description: str,
) -> LedgerEntry:
    return LedgerEntry.objects.create(
        player=player,
        round=current_round,
        kind=kind,
        amount_cents=amount_cents,
        balance_after_cents=player.balance_cents,
        description=description,
    )


def test_house_account_derives_operating_winnings_from_player_ledger() -> None:
    player = create_player(Device.objects.create(), "Counterparty")
    racer = Racer.objects.create(name="Winner", slug="house-winner", sprite_key="winner")
    current_round = settled_round(number=7, winner=racer)
    entries = [
        (LedgerEntry.Kind.STAKE, -1_000, "Stake"),
        (LedgerEntry.Kind.PAYOUT, 2_500, "Payout"),
        (LedgerEntry.Kind.REFUND, 100, "Refund"),
        (LedgerEntry.Kind.ITEM, -2_000, "Potion"),
        (LedgerEntry.Kind.SEAT, -4_000, "Seat"),
        (LedgerEntry.Kind.UPGRADE, -15_000, "Upgrade"),
        (LedgerEntry.Kind.BAILOUT, 2_000, "Medic"),
    ]
    for kind, amount_cents, description in entries:
        ledger(
            player=player,
            current_round=current_round,
            kind=kind,
            amount_cents=amount_cents,
            description=description,
        )
    LedgerEntry.objects.create(
        player=player,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        amount_cents=500,
        balance_after_cents=player.balance_cents,
        description="Admin credit",
    )

    summary = house_account_summary()

    assert summary.breakdown.stakes_collected_cents == 1_000
    assert summary.breakdown.payouts_paid_cents == 2_500
    assert summary.breakdown.refunds_paid_cents == 100
    assert summary.breakdown.betting_net_cents == -1_600
    assert summary.breakdown.commerce_revenue_cents == 21_000
    assert summary.breakdown.bailouts_paid_cents == 2_000
    assert summary.breakdown.operating_net_cents == 17_400
    assert summary.opening_grants_cents == 20_000
    assert summary.admin_adjustments_cents == -500
    assert summary.settled_rounds == 1
    assert summary.house_win_rounds == 0
    assert summary.operating_transactions == len(entries)

    history = house_round_history()
    assert len(history) == 1
    assert history[0].round_number == 7
    assert history[0].winner_name == "Winner"
    assert history[0].house_won is False
    assert history[0].breakdown.operating_net_cents == 17_400


def test_house_round_history_marks_no_finisher_and_recent_tape_inverts_signs() -> None:
    player = create_player(Device.objects.create(), "House Food")
    current_round = settled_round(number=9, winner=None)
    ledger(
        player=player,
        current_round=current_round,
        kind=LedgerEntry.Kind.STAKE,
        amount_cents=-750,
        description="No-finisher stake",
    )
    ledger(
        player=player,
        current_round=current_round,
        kind=LedgerEntry.Kind.BAILOUT,
        amount_cents=2_000,
        description="Bandages",
    )

    history = house_round_history()
    transactions = recent_house_transactions()

    assert history[0].house_won is True
    assert history[0].winner_name is None
    assert history[0].breakdown.operating_net_cents == -1_250
    assert transactions[0].label == "Track Medic payment"
    assert transactions[0].house_delta_cents == -2_000
    assert transactions[1].label == "Stake collected"
    assert transactions[1].house_delta_cents == 750


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "$0"),
        (1_050, "$10.50"),
        (-12_345, "−$123.45"),
        (1_000_000, "$10,000"),
    ],
)
def test_format_money(cents: int, expected: str) -> None:
    assert format_money(cents) == expected
