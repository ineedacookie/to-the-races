from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.betting.models import LedgerEntry
from apps.players.models import Player
from apps.racing.models import Round, RoundSeatClaim, SpectatorSeatDefinition


class SeatClaimError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SeatClaimReceipt:
    claim_id: int
    balance_cents: int
    seat_name: str
    seat_color: str
    price_paid_cents: int
    duplicate: bool = False


def _receipt(
    claim: RoundSeatClaim,
    balance_cents: int,
    *,
    duplicate: bool = False,
) -> SeatClaimReceipt:
    return SeatClaimReceipt(
        claim_id=claim.pk,
        balance_cents=balance_cents,
        seat_name=claim.seat.name,
        seat_color=claim.seat.color,
        price_paid_cents=claim.price_paid_cents,
        duplicate=duplicate,
    )


@transaction.atomic
def claim_seat(
    *,
    player: Player,
    round_id: int,
    seat_slug: str,
    client_request_id: uuid.UUID,
) -> SeatClaimReceipt:
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    existing = (
        RoundSeatClaim.objects.select_related("seat")
        .filter(player=locked_player, client_request_id=client_request_id)
        .first()
    )
    if existing is not None:
        return _receipt(existing, locked_player.balance_cents, duplicate=True)

    try:
        current_round = Round.objects.select_for_update().get(pk=round_id)
    except Round.DoesNotExist as error:
        raise SeatClaimError("unknown_round", "That round is not active.") from error

    if current_round.state != Round.State.OPEN or timezone.now() >= current_round.locks_at:
        raise SeatClaimError("betting_closed", "Seats can only be claimed while betting is open.")

    try:
        seat = SpectatorSeatDefinition.objects.get(slug=seat_slug, active=True)
    except SpectatorSeatDefinition.DoesNotExist as error:
        raise SeatClaimError("unknown_seat", "That seat is not available.") from error

    if locked_player.balance_cents < seat.price_cents:
        raise SeatClaimError(
            "insufficient_funds",
            f"You need {seat.price_cents // 100} dollars in available fun money.",
        )

    if RoundSeatClaim.objects.filter(round=current_round, seat=seat).exists():
        raise SeatClaimError("seat_taken", "That seat has already been claimed this round.")

    if RoundSeatClaim.objects.filter(player=locked_player, round=current_round).exists():
        raise SeatClaimError("seat_already_claimed", "You already claimed a seat this round.")

    claim = RoundSeatClaim.objects.create(
        player=locked_player,
        round=current_round,
        seat=seat,
        price_paid_cents=seat.price_cents,
        client_request_id=client_request_id,
    )
    locked_player.balance_cents -= seat.price_cents
    locked_player.save(update_fields=["balance_cents", "updated_at"])
    LedgerEntry.objects.create(
        player=locked_player,
        round=current_round,
        kind=LedgerEntry.Kind.SEAT,
        amount_cents=-seat.price_cents,
        balance_after_cents=locked_player.balance_cents,
        description=f"Claimed {seat.name}",
    )
    return _receipt(claim, locked_player.balance_cents)
