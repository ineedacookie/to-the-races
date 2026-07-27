from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.betting.models import Bet, LedgerEntry
from apps.players.models import Player
from apps.racing.models import RaceEntry, Round, RoundSeatClaim


class BetPlacementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


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
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    existing = (
        Bet.objects.select_related("race_entry__racer")
        .filter(player=locked_player, client_request_id=client_request_id)
        .first()
    )
    if existing is not None:
        return _receipt(existing, locked_player.balance_cents, duplicate=True)

    if amount_cents <= 0:
        raise BetPlacementError("invalid_amount", "The stake must be greater than zero.")

    try:
        race_entry = RaceEntry.objects.select_related("race__round", "racer").get(
            pk=race_entry_id
        )
    except RaceEntry.DoesNotExist as error:
        raise BetPlacementError("unknown_racer", "That racer is not in this round.") from error

    current_round = Round.objects.select_for_update().get(pk=race_entry.race.round_id)
    if current_round.state != Round.State.OPEN or timezone.now() >= current_round.locks_at:
        raise BetPlacementError("betting_closed", "Betting is closed for this race.")

    bet = Bet.objects.create(
        player=locked_player,
        round=current_round,
        race_entry=race_entry,
        client_request_id=client_request_id,
        amount_cents=amount_cents,
        decimal_odds=race_entry.odds,
    )
    locked_player.balance_cents -= amount_cents
    locked_player.save(update_fields=["balance_cents", "updated_at"])
    LedgerEntry.objects.create(
        player=locked_player,
        round=current_round,
        bet=bet,
        kind=LedgerEntry.Kind.STAKE,
        amount_cents=-amount_cents,
        balance_after_cents=locked_player.balance_cents,
        description=f"Winner bet on {race_entry.racer.name}",
    )
    return _receipt(bet, locked_player.balance_cents)


@transaction.atomic
def settle_round(round_id: int) -> dict[int, int]:
    current_round = Round.objects.select_for_update().select_related("race").get(pk=round_id)
    if current_round.settled_at is not None:
        player_ids = current_round.bets.values_list("player_id", flat=True).distinct()
        return {
            player.pk: player.balance_cents
            for player in Player.objects.filter(pk__in=player_ids)
        }
    if current_round.race.completed_at is None:
        raise RuntimeError("Cannot settle a race before its simulation is complete.")

    winner = current_round.race.entries.filter(finish_place=1).first()
    changed_player_ids: set[int] = set()
    seat_perks = {
        claim.player_id: (claim.seat.payout_bonus_bps, claim.seat.name)
        for claim in RoundSeatClaim.objects.filter(round=current_round).select_related("seat")
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
                (
                    Decimal(profit)
                    * Decimal(seat_bonus_bps)
                    / Decimal(10_000)
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            payout = base_payout + seat_bonus
            locked_player = Player.objects.select_for_update().get(pk=bet.player_id)
            locked_player.balance_cents += payout
            locked_player.save(update_fields=["balance_cents", "updated_at"])
            LedgerEntry.objects.create(
                player=locked_player,
                round=current_round,
                bet=bet,
                kind=LedgerEntry.Kind.PAYOUT,
                amount_cents=payout,
                balance_after_cents=locked_player.balance_cents,
                description=(
                    f"{bet.race_entry.racer.name} won at {bet.decimal_odds}x"
                    + (
                        f" + {seat_name} bonus"
                        if seat_bonus > 0
                        else ""
                    )
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
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    locked_player.balance_cents += amount_cents
    locked_player.save(update_fields=["balance_cents", "updated_at"])
    LedgerEntry.objects.create(
        player=locked_player,
        kind=LedgerEntry.Kind.ADJUSTMENT,
        amount_cents=amount_cents,
        balance_after_cents=locked_player.balance_cents,
        description=description,
    )
    return locked_player
