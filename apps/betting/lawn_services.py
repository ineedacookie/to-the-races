from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.betting.bailout_services import (
    BAILOUT_BALANCE_LIMIT_CENTS,
    _current_or_show_round,
)
from apps.betting.models import BailoutSession, LawnMowingSession, LedgerEntry
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.players.models import Player
from apps.racing.models import Round

LAWN_COLUMNS = 10
LAWN_ROWS = 6
LAWN_CELL_COUNT = LAWN_COLUMNS * LAWN_ROWS
LAWN_REWARD_CENTS = 2_000


class LawnMowingError(ServiceError):
    pass


@dataclass(frozen=True, slots=True)
class LawnMowingReceipt:
    session_id: int
    round_id: int
    mowed_cells: list[int]
    completed: bool
    balance_cents: int
    reward_cents: int
    duplicate: bool = False


def _receipt(
    session: LawnMowingSession,
    *,
    balance_cents: int,
    duplicate: bool = False,
) -> LawnMowingReceipt:
    completed = session.completed_at is not None
    return LawnMowingReceipt(
        session_id=session.pk,
        round_id=session.round_id,
        mowed_cells=sorted(session.mowed_cells),
        completed=completed,
        balance_cents=balance_cents,
        reward_cents=LAWN_REWARD_CENTS if completed else 0,
        duplicate=duplicate,
    )


def _eligible_for_assistance(player: Player, current_round: Round) -> bool:
    if player.balance_cents < BAILOUT_BALANCE_LIMIT_CENTS:
        return True
    return BailoutSession.objects.filter(player=player, round=current_round).exists()


@transaction.atomic
def start_lawn_mowing(
    *,
    player: Player,
    round_id: int,
    client_request_id: uuid.UUID,
) -> LawnMowingReceipt:
    locked_player = lock_player(player)
    prior_request = LawnMowingSession.objects.filter(
        player=locked_player,
        start_request_id=client_request_id,
    ).first()
    if prior_request is not None:
        return _receipt(
            prior_request,
            balance_cents=locked_player.balance_cents,
            duplicate=True,
        )

    current_round = _current_or_show_round(round_id)
    if current_round is None:
        raise LawnMowingError("stale_round", "Lawn mowing is only available this round.")
    if not _eligible_for_assistance(locked_player, current_round):
        raise LawnMowingError(
            "balance_too_high",
            "Lawn mowing is only available below $10.",
        )
    if LawnMowingSession.objects.filter(player=locked_player, round=current_round).exists():
        raise LawnMowingError("lawn_unavailable", "You already mowed a lawn this round.")

    try:
        session = LawnMowingSession.objects.create(
            player=locked_player,
            round=current_round,
            start_request_id=client_request_id,
        )
    except IntegrityError as error:
        raise LawnMowingError(
            "lawn_unavailable",
            "You already mowed a lawn this round.",
        ) from error
    return _receipt(session, balance_cents=locked_player.balance_cents)


@transaction.atomic
def mow_lawn_cells(
    *,
    player: Player,
    session_id: int,
    cell_indices: list[int],
) -> LawnMowingReceipt:
    locked_player = lock_player(player)
    try:
        session = (
            LawnMowingSession.objects.select_for_update()
            .select_related("round")
            .get(pk=session_id, player=locked_player)
        )
    except LawnMowingSession.DoesNotExist as error:
        raise LawnMowingError("unknown_session", "That lawn job was not found.") from error

    if _current_or_show_round(session.round_id) is None:
        raise LawnMowingError("stale_session", "That lawn job belongs to a previous round.")
    if session.completed_at is not None:
        return _receipt(session, balance_cents=locked_player.balance_cents, duplicate=True)
    if not cell_indices or any(
        isinstance(index, bool) or index < 0 or index >= LAWN_CELL_COUNT for index in cell_indices
    ):
        raise LawnMowingError("invalid_cells", "That mowing path is invalid.")

    mowed = set(session.mowed_cells)
    mowed.update(cell_indices)
    session.mowed_cells = sorted(mowed)
    update_fields = ["mowed_cells"]
    if len(mowed) == LAWN_CELL_COUNT:
        session.reward_credited = True
        session.completed_at = timezone.now()
        update_fields.extend(["reward_credited", "completed_at"])
        change_balance(
            player=locked_player,
            current_round=session.round,
            kind=LedgerEntry.Kind.LAWN,
            amount_cents=LAWN_REWARD_CENTS,
            description="Mowed the pixel lawn",
        )
    session.save(update_fields=update_fields)
    return _receipt(session, balance_cents=locked_player.balance_cents)


def serialize_lawn_mowing(
    *,
    player: Player,
    current_round: Round | None,
) -> dict[str, object]:
    if current_round is None:
        return {"eligible": False, "session": None, "stale": False}

    session = LawnMowingSession.objects.filter(player=player, round=current_round).first()
    if session is not None:
        completed = session.completed_at is not None
        return {
            "eligible": not completed,
            "session": {
                "id": session.pk,
                "round_id": session.round_id,
                "completed": completed,
                "mowed_cells": sorted(session.mowed_cells),
                "cell_count": LAWN_CELL_COUNT,
                "columns": LAWN_COLUMNS,
                "rows": LAWN_ROWS,
                "reward_cents": LAWN_REWARD_CENTS,
            },
            "stale": False,
        }

    eligible = (
        player.balance_cents < BAILOUT_BALANCE_LIMIT_CENTS
        or BailoutSession.objects.filter(player=player, round=current_round).exists()
    )
    return {"eligible": eligible, "session": None, "stale": False}
