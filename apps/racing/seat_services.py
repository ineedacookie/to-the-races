from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.betting.models import LedgerEntry
from apps.betting.money import available_funds_message, whole_dollars
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.core.idempotency import existing_receipt
from apps.players.models import Player
from apps.racing.models import (
    RoomSettings,
    Round,
    RoundSeatMarket,
    SeatOwnership,
    SeatTakeoverReceipt,
    SpectatorSeatDefinition,
)
from apps.racing.round_guards import locked_round, require_betting_open

TAKEOVER_PRICE_INCREMENT_CENTS = 500
DISPLACED_OWNER_REFUND_BPS = 5_000


class SeatClaimError(ServiceError):
    pass


@dataclass(frozen=True, slots=True)
class SeatClaimReceipt:
    claim_id: int
    balance_cents: int
    seat_name: str
    seat_color: str
    price_paid_cents: int
    next_price_cents: int
    duplicate: bool = False


def _receipt(
    takeover: SeatTakeoverReceipt,
    balance_cents: int,
    *,
    next_price_cents: int,
    duplicate: bool = False,
) -> SeatClaimReceipt:
    return SeatClaimReceipt(
        claim_id=takeover.pk,
        balance_cents=balance_cents,
        seat_name=takeover.seat.name,
        seat_color=takeover.seat.color,
        price_paid_cents=takeover.price_paid_cents,
        next_price_cents=next_price_cents,
        duplicate=duplicate,
    )


def _duplicate_receipt(takeover: SeatTakeoverReceipt, balance_cents: int) -> SeatClaimReceipt:
    market = RoundSeatMarket.objects.filter(
        round_id=takeover.round_id,
        seat_id=takeover.seat_id,
    ).first()
    next_price_cents = (
        market.current_price_cents
        if market is not None
        else takeover.seat.price_cents + TAKEOVER_PRICE_INCREMENT_CENTS
    )
    return _receipt(
        takeover,
        balance_cents,
        next_price_cents=next_price_cents,
        duplicate=True,
    )


def ensure_round_seat_markets(current_round: Round) -> None:
    active_seats = SpectatorSeatDefinition.objects.filter(active=True).order_by(
        "sort_order",
        "name",
        "pk",
    )
    existing_seat_ids = set(
        RoundSeatMarket.objects.filter(round=current_round).values_list("seat_id", flat=True)
    )
    to_create = [
        RoundSeatMarket(
            round=current_round,
            seat=seat,
            current_price_cents=seat.price_cents,
            takeover_count=0,
        )
        for seat in active_seats
        if seat.pk not in existing_seat_ids
    ]
    if to_create:
        RoundSeatMarket.objects.bulk_create(to_create, ignore_conflicts=True)


@transaction.atomic
def claim_seat(
    *,
    player: Player,
    round_id: int,
    seat_slug: str,
    expected_price_cents: int,
    client_request_id: uuid.UUID,
) -> SeatClaimReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        SeatTakeoverReceipt.objects.select_related("seat").filter(
            player=locked_player,
            client_request_id=client_request_id,
        ),
        lambda takeover: _duplicate_receipt(takeover, locked_player.balance_cents),
    )
    if duplicate is not None:
        return duplicate

    current_round = locked_round(round_id, error_type=SeatClaimError)
    require_betting_open(
        current_round=current_round,
        room=RoomSettings.load(),
        error_type=SeatClaimError,
        message="Seats can only be claimed while betting is open.",
    )

    try:
        seat = SpectatorSeatDefinition.objects.get(slug=seat_slug, active=True)
    except SpectatorSeatDefinition.DoesNotExist as error:
        raise SeatClaimError("unknown_seat", "That seat is not available.") from error

    ensure_round_seat_markets(current_round)
    try:
        market = RoundSeatMarket.objects.select_for_update().get(
            round=current_round,
            seat=seat,
        )
    except RoundSeatMarket.DoesNotExist as error:
        raise SeatClaimError("unknown_seat", "That seat is not available.") from error

    if expected_price_cents != market.current_price_cents:
        raise SeatClaimError(
            "stale_price",
            (
                f"That seat now costs {whole_dollars(market.current_price_cents)} dollars. "
                "Refresh and try again."
            ),
        )

    relevant_ownerships = list(
        SeatOwnership.objects.select_for_update()
        .filter(Q(seat=seat) | Q(player=locked_player))
        .select_related("player", "seat")
        .order_by("pk")
    )
    seat_ownership = next(
        (ownership for ownership in relevant_ownerships if ownership.seat_id == seat.pk),
        None,
    )
    if seat_ownership is not None and seat_ownership.player_id == locked_player.pk:
        raise SeatClaimError("self_purchase", "You already own that seat.")

    previous_owner_id = seat_ownership.player_id if seat_ownership is not None else None
    player_ownership = next(
        (ownership for ownership in relevant_ownerships if ownership.player_id == locked_player.pk),
        None,
    )
    if player_ownership is not None:
        player_ownership.delete()

    price_paid_cents = market.current_price_cents
    change_balance(
        player=locked_player,
        current_round=current_round,
        kind=LedgerEntry.Kind.SEAT,
        amount_cents=-price_paid_cents,
        description=f"Took over {seat.name}",
        error_type=SeatClaimError,
        insufficient_message=available_funds_message(price_paid_cents),
    )

    if seat_ownership is not None:
        assert previous_owner_id is not None
        previous_owner = lock_player(previous_owner_id)
        previous_purchase = (
            SeatTakeoverReceipt.objects.filter(player=previous_owner, seat=seat)
            .order_by("-created_at", "-pk")
            .first()
        )
        if previous_purchase is None:
            raise RuntimeError("Seat owner is missing their acquisition receipt.")
        refund_cents = (
            previous_purchase.price_paid_cents * DISPLACED_OWNER_REFUND_BPS // 10_000
        )
        change_balance(
            player=previous_owner,
            current_round=current_round,
            kind=LedgerEntry.Kind.REFUND,
            amount_cents=refund_cents,
            description=f"50% refund after losing {seat.name}",
        )
        seat_ownership.player = locked_player
        seat_ownership.acquired_at = timezone.now()
        seat_ownership.save(update_fields=["player", "acquired_at"])
    else:
        SeatOwnership.objects.create(player=locked_player, seat=seat)

    takeover = SeatTakeoverReceipt.objects.create(
        player=locked_player,
        round=current_round,
        seat=seat,
        previous_owner_id=previous_owner_id,
        price_paid_cents=price_paid_cents,
        client_request_id=client_request_id,
    )

    market.current_price_cents += TAKEOVER_PRICE_INCREMENT_CENTS
    market.takeover_count += 1
    market.save(update_fields=["current_price_cents", "takeover_count"])

    return _receipt(
        takeover,
        locked_player.balance_cents,
        next_price_cents=market.current_price_cents,
    )
