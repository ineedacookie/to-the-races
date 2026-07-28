from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.betting.models import Bet, LedgerEntry
from apps.betting.money import stake_cap_message
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.core.idempotency import existing_receipt
from apps.players.models import Player
from apps.racing.models import RaceEntry, RoomSettings, Round, SeatOwnership
from apps.racing.round_guards import locked_round, require_betting_open


class BetPlacementError(ServiceError):
    pass


class BalanceAdjustmentError(ServiceError):
    pass


@dataclass(frozen=True, slots=True)
class BetReceipt:
    bet_id: int
    balance_cents: int
    amount_cents: int
    racer_name: str
    decimal_odds: str
    duplicate: bool = False


def _receipt(bet: Bet, balance_cents: int, *, duplicate: bool = False) -> BetReceipt:
    return BetReceipt(
        bet_id=bet.pk,
        balance_cents=balance_cents,
        amount_cents=bet.amount_cents,
        racer_name=bet.race_entry.racer.name,
        decimal_odds=str(bet.decimal_odds),
        duplicate=duplicate,
    )


@transaction.atomic
def place_bet(
    *,
    player: Player,
    race_entry_id: int,
    amount_cents: int,
    client_request_id: uuid.UUID,
) -> BetReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        Bet.objects.select_related("race_entry__racer").filter(
            player=locked_player,
            client_request_id=client_request_id,
        ),
        lambda bet: _receipt(bet, locked_player.balance_cents, duplicate=True),
    )
    if duplicate is not None:
        return duplicate

    if amount_cents <= 0:
        raise BetPlacementError("invalid_amount", "The stake must be greater than zero.")

    try:
        race_entry = RaceEntry.objects.select_related("race__round", "racer").get(pk=race_entry_id)
    except RaceEntry.DoesNotExist as error:
        raise BetPlacementError("unknown_racer", "That racer is not in this round.") from error

    current_round = locked_round(race_entry.race.round_id, error_type=BetPlacementError)
    room = RoomSettings.load()
    require_betting_open(
        current_round=current_round,
        room=room,
        error_type=BetPlacementError,
        message="Betting is closed for this race.",
    )
    round_staked = (
        Bet.objects.filter(player=locked_player, round=current_round)
        .aggregate(total=Sum("amount_cents"))
        .get("total")
        or 0
    )
    if round_staked + amount_cents > room.max_round_stake_cents:
        remaining = max(room.max_round_stake_cents - round_staked, 0)
        raise BetPlacementError(
            "round_stake_cap",
            stake_cap_message(
                cap_cents=room.max_round_stake_cents,
                remaining_cents=remaining,
            ),
        )

    bet = Bet.objects.create(
        player=locked_player,
        round=current_round,
        race_entry=race_entry,
        client_request_id=client_request_id,
        amount_cents=amount_cents,
        decimal_odds=race_entry.odds,
    )
    change_balance(
        player=locked_player,
        current_round=current_round,
        bet=bet,
        kind=LedgerEntry.Kind.STAKE,
        amount_cents=-amount_cents,
        description=f"Winner bet on {race_entry.racer.name}",
        error_type=BetPlacementError,
    )
    return _receipt(bet, locked_player.balance_cents)


@transaction.atomic
def settle_round(round_id: int) -> dict[int, int]:
    current_round = Round.objects.select_for_update().select_related("race").get(pk=round_id)
    if current_round.settled_at is not None:
        player_ids = current_round.bets.values_list("player_id", flat=True).distinct()
        return {
            player.pk: player.balance_cents for player in Player.objects.filter(pk__in=player_ids)
        }
    if current_round.race.completed_at is None:
        raise RuntimeError("Cannot settle a race before its simulation is complete.")

    winner = current_round.race.entries.filter(finish_place=1).first()
    changed_player_ids: set[int] = set()
    seat_perks = {
        ownership.player_id: (ownership.seat.payout_bonus_bps, ownership.seat.name)
        for ownership in SeatOwnership.objects.select_related("seat")
    }
    bets = current_round.bets.select_related("player", "race_entry__racer").filter(
        status=Bet.Status.PENDING
    )
    for bet in bets:
        changed_player_ids.add(bet.player_id)
        if winner is not None and bet.race_entry_id == winner.pk:
            base_payout = int(
                (Decimal(bet.amount_cents) * bet.decimal_odds).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )
            seat_bonus_bps, seat_name = seat_perks.get(bet.player_id, (0, ""))
            profit = max(base_payout - bet.amount_cents, 0)
            seat_bonus = int(
                (Decimal(profit) * Decimal(seat_bonus_bps) / Decimal(10_000)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            payout = base_payout + seat_bonus
            locked_player = lock_player(bet.player_id)
            change_balance(
                player=locked_player,
                current_round=current_round,
                bet=bet,
                kind=LedgerEntry.Kind.PAYOUT,
                amount_cents=payout,
                description=(
                    f"{bet.race_entry.racer.name} won at {bet.decimal_odds}x"
                    + (f" + {seat_name} bonus" if seat_bonus > 0 else "")
                ),
            )
            bet.status = Bet.Status.WON
            bet.payout_cents = payout
        else:
            bet.status = Bet.Status.LOST
        bet.settled_at = timezone.now()
        bet.save(update_fields=["status", "payout_cents", "settled_at"])

    current_round.settled_at = timezone.now()
    current_round.save(update_fields=["settled_at"])
    return {
        player.pk: player.balance_cents
        for player in Player.objects.filter(pk__in=changed_player_ids)
    }


@transaction.atomic
def adjust_balance(*, player: Player, amount_cents: int, description: str) -> Player:
    locked_player = lock_player(player)
    change_balance(
        player=locked_player,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        amount_cents=amount_cents,
        description=description,
        error_type=BalanceAdjustmentError,
        insufficient_message="That adjustment would leave the player with a negative balance.",
    )
    return locked_player
