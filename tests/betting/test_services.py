from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from apps.betting.models import Bet, LedgerEntry
from apps.betting.money import stake_cap_message
from apps.betting.services import (
    BalanceAdjustmentError,
    BetPlacementError,
    adjust_balance,
    place_bet,
    settle_round,
)
from apps.players.models import Device, Player
from apps.players.services import create_player
from apps.racing.models import (
    RaceEntry,
    RoomSettings,
    Round,
    SeatOwnership,
    SpectatorSeatDefinition,
)
from apps.racing.serializers import build_live_state
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from tests.factories import open_round_with_entries

pytestmark = pytest.mark.django_db


def test_stake_cap_message_preserves_cent_remainders() -> None:
    assert stake_cap_message(cap_cents=15_000, remaining_cents=45) == (
        "That exceeds this round's $150 stake cap. You may stake $0.45 more."
    )


def open_round(
    *,
    opening_balance_cents: int = 1_000,
    max_round_stake_cents: int = 50_000,
) -> tuple[Round, RaceEntry, RaceEntry]:
    return open_round_with_entries(
        opening_balance_cents=opening_balance_cents,
        max_round_stake_cents=max_round_stake_cents,
        second_odds="4.50",
    )


def test_multiple_bets_respect_aggregate_round_cap() -> None:
    _round, first, second = open_round(
        opening_balance_cents=55_000,
        max_round_stake_cents=50_000,
    )
    player = create_player(Device.objects.create(), "Cap Tester")

    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=30_000,
        client_request_id=uuid.uuid4(),
    )
    place_bet(
        player=player,
        race_entry_id=second.pk,
        amount_cents=20_000,
        client_request_id=uuid.uuid4(),
    )

    player.refresh_from_db()
    assert player.balance_cents == 5_000
    assert player.bets.count() == 2

    with pytest.raises(BetPlacementError) as capped:
        place_bet(
            player=player,
            race_entry_id=first.pk,
            amount_cents=100,
            client_request_id=uuid.uuid4(),
        )
    assert capped.value.code == "round_stake_cap"


def test_bet_rejects_insufficient_funds() -> None:
    _round, first, _second = open_round(opening_balance_cents=500)
    player = create_player(Device.objects.create(), "Broke Bettor")

    with pytest.raises(BetPlacementError) as caught:
        place_bet(
            player=player,
            race_entry_id=first.pk,
            amount_cents=600,
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "insufficient_funds"

    player.refresh_from_db()
    assert player.balance_cents == 500
    assert player.bets.count() == 0


def test_bet_accepts_a_fractional_dollar_balance() -> None:
    _round, first, _second = open_round(opening_balance_cents=45)
    player = create_player(Device.objects.create(), "Penny Bettor")

    receipt = place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=45,
        client_request_id=uuid.uuid4(),
    )

    player.refresh_from_db()
    assert receipt.amount_cents == 45
    assert player.balance_cents == 0


def test_bet_rejects_requests_while_room_is_paused() -> None:
    _round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Paused Bettor")
    room = RoomSettings.load()
    room.is_paused = True
    room.save(update_fields=["is_paused"])

    with pytest.raises(BetPlacementError) as caught:
        place_bet(
            player=player,
            race_entry_id=first.pk,
            amount_cents=100,
            client_request_id=uuid.uuid4(),
        )

    assert caught.value.code == "betting_closed"


def test_bet_rejects_requests_after_the_race_starts() -> None:
    current_round, first, _second = open_round()
    player = create_player(Device.objects.create(), "Late Bettor")
    current_round.state = Round.State.RACING
    current_round.save(update_fields=["state"])

    with pytest.raises(BetPlacementError) as caught:
        place_bet(
            player=player,
            race_entry_id=first.pk,
            amount_cents=100,
            client_request_id=uuid.uuid4(),
        )

    assert caught.value.code == "betting_closed"
    assert player.bets.count() == 0


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


def test_stakes_above_round_cap_are_rejected() -> None:
    _round, first, _second = open_round(
        opening_balance_cents=60_000,
        max_round_stake_cents=50_000,
    )
    player = create_player(Device.objects.create(), "Uncapped Tester")

    with pytest.raises(BetPlacementError) as caught:
        place_bet(
            player=player,
            race_entry_id=first.pk,
            amount_cents=50_100,
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "round_stake_cap"

    player.refresh_from_db()
    assert player.balance_cents == 60_000
    assert player.bets.count() == 0


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
    SeatOwnership.objects.create(player=player, seat=seat)
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


def test_live_state_exposes_round_stake_cap_and_remaining() -> None:
    _round, first, _second = open_round(
        opening_balance_cents=20_000,
        max_round_stake_cents=50_000,
    )
    player = create_player(Device.objects.create(), "State Watcher")
    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=12_000,
        client_request_id=uuid.uuid4(),
    )

    live_state = build_live_state(player_id=player.pk)

    assert live_state["room"]["max_round_stake_cents"] == 50_000
    assert live_state["player"]["round_staked_cents"] == 12_000
    assert live_state["player"]["round_stake_remaining_cents"] == 38_000


def test_adjust_balance_rejects_negative_result() -> None:
    player = create_player(Device.objects.create(), "Admin Target")

    with pytest.raises(BalanceAdjustmentError) as caught:
        adjust_balance(player=player, amount_cents=-20_001, description="Too much debit")
    assert caught.value.code == "insufficient_funds"


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


@pytest.mark.django_db(transaction=True)
def test_concurrent_bets_cannot_exceed_round_cap() -> None:
    _round, first, second = open_round(max_round_stake_cents=50_000)
    player = create_player(Device.objects.create(), "Parallel Bettor")
    player.balance_cents = 100_000
    player.save(update_fields=["balance_cents", "updated_at"])
    barrier = Barrier(2)
    outcomes: list[str] = []

    def submit(entry_id: int, amount_cents: int) -> None:
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            place_bet(
                player=Player.objects.get(pk=player.pk),
                race_entry_id=entry_id,
                amount_cents=amount_cents,
                client_request_id=uuid.uuid4(),
            )
            outcomes.append("ok")
        except BetPlacementError as error:
            outcomes.append(error.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.map(
            lambda args: submit(*args),
            [(first.pk, 30_000), (second.pk, 30_000)],
        )

    player.refresh_from_db()
    total_staked = (
        Bet.objects.filter(player=player, round=_round)
        .aggregate(total=Sum("amount_cents"))
        .get("total")
        or 0
    )
    assert total_staked <= 50_000
    assert player.balance_cents == 100_000 - total_staked
    assert outcomes.count("ok") == 1
    assert outcomes.count("round_stake_cap") == 1


@pytest.mark.django_db(transaction=True)
def test_negative_balance_migration_resets_legacy_rows() -> None:
    call_command("migrate", "players", "0003", verbosity=0)
    old_apps = MigrationExecutor(connection).loader.project_state(
        [("players", "0003_remove_player_device_device_player")]
    ).apps
    historical_player = old_apps.get_model("players", "Player")
    player = historical_player.objects.create(nickname="Legacy Debtor", balance_cents=-750)

    call_command("migrate", "players", "0004", verbosity=0)

    player.refresh_from_db()
    assert player.balance_cents == 0

    player.balance_cents = -1
    with pytest.raises(IntegrityError):
        player.save(update_fields=["balance_cents"])

    call_command("migrate", verbosity=0)


@pytest.mark.django_db(transaction=True)
def test_balance_reset_migration_sets_every_player_to_100_dollars() -> None:
    call_command("migrate", "players", "0004", verbosity=0)
    old_apps = MigrationExecutor(connection).loader.project_state(
        [("players", "0004_player_balance_non_negative")]
    ).apps
    historical_player = old_apps.get_model("players", "Player")
    players = [
        historical_player.objects.create(nickname="Low Balance", balance_cents=0),
        historical_player.objects.create(nickname="Exact Balance", balance_cents=10_000),
        historical_player.objects.create(nickname="High Balance", balance_cents=250_000),
    ]

    call_command("migrate", "players", "0005", verbosity=0)

    assert list(
        historical_player.objects.filter(pk__in=[player.pk for player in players])
        .order_by("pk")
        .values_list("balance_cents", flat=True)
    ) == [10_000, 10_000, 10_000]

    call_command("migrate", verbosity=0)


class PlayerBalanceConstraintTests(TestCase):
    def test_player_balance_cannot_be_saved_negative(self) -> None:
        player = Player.objects.create(nickname="Constraint Check", balance_cents=100)
        player.balance_cents = -1
        with pytest.raises(IntegrityError):
            player.save()
