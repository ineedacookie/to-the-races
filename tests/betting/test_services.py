from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from apps.betting.models import Bet, LedgerEntry
from apps.betting.services import place_bet, settle_round
from apps.players.models import Device, Player
from apps.players.services import create_player
from apps.racing.models import (
    Race,
    RaceEntry,
    Racer,
    RoomSettings,
    Round,
    RoundSeatClaim,
    SpectatorSeatDefinition,
)
from django.db import close_old_connections
from django.utils import timezone

pytestmark = pytest.mark.django_db


def open_round(
    *,
    opening_balance_cents: int = 1_000,
) -> tuple[Round, RaceEntry, RaceEntry]:
    room = RoomSettings.load()
    room.opening_balance_cents = opening_balance_cents
    room.save()
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(minutes=1),
        race_starts_at=now + timedelta(minutes=2),
        race_ends_at=now + timedelta(minutes=3),
        results_end_at=now + timedelta(minutes=4),
    )
    race = Race.objects.create(round=current_round)
    first_racer = Racer.objects.create(
        name="First",
        slug="first",
        sprite_key="first",
    )
    second_racer = Racer.objects.create(
        name="Second",
        slug="second",
        sprite_key="second",
    )
    first = RaceEntry.objects.create(
        race=race,
        racer=first_racer,
        lane=1,
        odds=Decimal("3.00"),
    )
    second = RaceEntry.objects.create(
        race=race,
        racer=second_racer,
        lane=2,
        odds=Decimal("4.50"),
    )
    return current_round, first, second


def test_multiple_picks_can_take_balance_negative() -> None:
    _round, first, second = open_round(opening_balance_cents=500)
    player = create_player(Device.objects.create(), "Negative Nancy")

    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=600,
        client_request_id=uuid.uuid4(),
    )
    place_bet(
        player=player,
        race_entry_id=second.pk,
        amount_cents=400,
        client_request_id=uuid.uuid4(),
    )

    player.refresh_from_db()
    assert player.balance_cents == -500
    assert player.bets.count() == 2
    assert list(player.ledger_entries.values_list("amount_cents", flat=True)) == [
        -400,
        -600,
        500,
    ]


def test_duplicate_request_is_idempotent() -> None:
    _round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Double Click")
    request_id = uuid.uuid4()

    original = place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=request_id,
    )
    duplicate = place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=request_id,
    )

    player.refresh_from_db()
    assert original.bet_id == duplicate.bet_id
    assert duplicate.duplicate is True
    assert player.balance_cents == 500
    assert Bet.objects.count() == 1
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.STAKE).count() == 1


def test_stakes_have_no_maximum_and_can_create_large_play_money_debt() -> None:
    _round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Uncapped Tester")

    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=250_000,
        client_request_id=uuid.uuid4(),
    )

    player.refresh_from_db()
    assert player.balance_cents == -249_000


def test_winner_receives_fixed_odds_payout() -> None:
    current_round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Winner")
    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )
    first.finish_place = 1
    first.finish_tick = 100
    first.save()
    current_round.race.completed_at = timezone.now()
    current_round.race.save(update_fields=["completed_at"])

    settle_round(current_round.pk)

    player.refresh_from_db()
    bet = player.bets.get()
    assert bet.status == Bet.Status.WON
    assert bet.payout_cents == 1_500
    assert player.balance_cents == 2_000


def test_grandstand_seat_adds_its_bonus_to_winning_profit() -> None:
    current_round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Throne Winner")
    seat = SpectatorSeatDefinition.objects.create(
        slug="test-throne",
        name="Test Throne",
        description="Adds 25% to winning profit.",
        sprite_key="mimic",
        price_cents=15_000,
        payout_bonus_bps=2_500,
    )
    RoundSeatClaim.objects.create(
        player=player,
        round=current_round,
        seat=seat,
        price_paid_cents=seat.price_cents,
    )
    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )
    first.finish_place = 1
    first.finish_tick = 100
    first.save(update_fields=["finish_place", "finish_tick"])
    current_round.race.completed_at = timezone.now()
    current_round.race.save(update_fields=["completed_at"])

    settle_round(current_round.pk)

    player.refresh_from_db()
    bet = player.bets.get()
    assert bet.payout_cents == 1_750
    assert player.balance_cents == 2_250
    assert player.ledger_entries.filter(description__contains="Test Throne bonus").exists()


def test_mixed_bets_report_the_final_balance_after_settlement() -> None:
    current_round, winner, loser = open_round()
    player = create_player(Device.objects.create(), "Split Ticket")
    place_bet(
        player=player,
        race_entry_id=loser.pk,
        amount_cents=200,
        client_request_id=uuid.uuid4(),
    )
    place_bet(
        player=player,
        race_entry_id=winner.pk,
        amount_cents=100,
        client_request_id=uuid.uuid4(),
    )
    winner.finish_place = 1
    winner.finish_tick = 100
    winner.save(update_fields=["finish_place", "finish_tick"])
    current_round.race.completed_at = timezone.now()
    current_round.race.save(update_fields=["completed_at"])

    changed_balances = settle_round(current_round.pk)

    player.refresh_from_db()
    assert player.balance_cents == 1_000
    assert changed_balances[player.pk] == player.balance_cents


def test_no_finisher_means_the_house_keeps_every_stake() -> None:
    current_round, first, _second = open_round()
    player = create_player(Device.objects.create(), "House Guest")
    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )
    current_round.race.completed_at = timezone.now()
    current_round.race.result = {"finish_order": [], "house_wins": True}
    current_round.race.save(update_fields=["completed_at", "result"])

    settle_round(current_round.pk)

    player.refresh_from_db()
    assert player.balance_cents == 500
    assert player.bets.get().status == Bet.Status.LOST
    assert not player.ledger_entries.filter(kind=LedgerEntry.Kind.PAYOUT).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_submissions_only_charge_once() -> None:
    _round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Two Thumbs")
    request_id = uuid.uuid4()
    barrier = Barrier(2)

    def submit() -> int:
        close_old_connections()
        barrier.wait(timeout=5)
        receipt = place_bet(
            player=Player.objects.get(pk=player.pk),
            race_entry_id=first.pk,
            amount_cents=500,
            client_request_id=request_id,
        )
        close_old_connections()
        return receipt.bet_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        bet_ids = list(pool.map(lambda _index: submit(), range(2)))

    player.refresh_from_db()
    assert len(set(bet_ids)) == 1
    assert player.balance_cents == 500
    assert player.bets.count() == 1
