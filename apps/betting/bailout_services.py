from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.betting.bailout_wounds import (
    BAILOUT_REWARD_CENTS,
    WoundCoordinate,
    generate_bailout_wounds,
    pick_bailout_race_entry,
)
from apps.betting.models import BailoutPatch, BailoutSession, LawnMowingSession, LedgerEntry
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.core.idempotency import create_idempotently, existing_receipt
from apps.players.models import Player
from apps.racing.models import RaceEntry, Round
from apps.racing.round_guards import active_show_round, latest_round

BAILOUT_BALANCE_LIMIT_CENTS = 1_000


class BailoutError(ServiceError):
    pass


def _current_or_show_round(round_id: int) -> Round | None:
    current_round = latest_round(for_update=True)
    if current_round is not None and current_round.pk == round_id:
        return current_round
    show_round = active_show_round(for_update=True)
    if show_round is not None and show_round.pk == round_id:
        return show_round
    return None


@dataclass(frozen=True, slots=True)
class BailoutStartReceipt:
    session_id: int
    round_id: int
    race_entry_id: int
    racer_name: str
    sprite_key: str
    wound_count: int
    wounds: list[WoundCoordinate]
    patched_indices: list[int]
    completed: bool
    balance_cents: int
    reward_cents: int
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class BailoutPatchReceipt:
    session_id: int
    wound_index: int
    patched_indices: list[int]
    completed: bool
    balance_cents: int
    reward_cents: int
    duplicate: bool = False


def _serialize_session(
    session: BailoutSession,
    *,
    patched_indices: list[int],
    balance_cents: int,
    duplicate: bool = False,
) -> BailoutStartReceipt:
    completed = session.completed_at is not None
    return BailoutStartReceipt(
        session_id=session.pk,
        round_id=session.round_id,
        race_entry_id=session.race_entry_id,
        racer_name=session.race_entry.racer.name,
        sprite_key=session.race_entry.racer.sprite_key,
        wound_count=session.wound_count,
        wounds=session.wounds,
        patched_indices=patched_indices,
        completed=completed,
        balance_cents=balance_cents,
        reward_cents=BAILOUT_REWARD_CENTS if completed else 0,
        duplicate=duplicate,
    )


def _serialize_patch(
    session: BailoutSession,
    *,
    wound_index: int,
    patched_indices: list[int],
    balance_cents: int,
    duplicate: bool = False,
) -> BailoutPatchReceipt:
    completed = session.completed_at is not None
    return BailoutPatchReceipt(
        session_id=session.pk,
        wound_index=wound_index,
        patched_indices=patched_indices,
        completed=completed,
        balance_cents=balance_cents,
        reward_cents=BAILOUT_REWARD_CENTS if completed else 0,
        duplicate=duplicate,
    )


def _patched_indices(session: BailoutSession) -> list[int]:
    return list(session.patches.order_by("wound_index").values_list("wound_index", flat=True))


def _maybe_complete_session(
    *,
    session: BailoutSession,
    locked_player: Player,
) -> None:
    if session.completed_at is not None or session.reward_credited:
        return
    if session.patches.count() < session.wound_count:
        return

    session.reward_credited = True
    session.completed_at = timezone.now()
    session.save(update_fields=["reward_credited", "completed_at"])
    change_balance(
        player=locked_player,
        current_round=session.round,
        kind=LedgerEntry.Kind.BAILOUT,
        amount_cents=BAILOUT_REWARD_CENTS,
        description=f"Track medic patched {session.race_entry.racer.name}",
    )


@transaction.atomic
def start_bailout(
    *,
    player: Player,
    round_id: int,
    client_request_id: uuid.UUID,
) -> BailoutStartReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        BailoutSession.objects.select_related("race_entry__racer", "round")
        .prefetch_related("patches")
        .filter(player=locked_player, start_request_id=client_request_id),
        lambda session: _serialize_session(
            session,
            patched_indices=_patched_indices(session),
            balance_cents=locked_player.balance_cents,
            duplicate=True,
        ),
    )
    if duplicate is not None:
        return duplicate

    current_round = _current_or_show_round(round_id)
    if current_round is None:
        raise BailoutError(
            "stale_round",
            "Track medic is only available for the current round.",
        )

    lawn_job_started = LawnMowingSession.objects.filter(
        player=locked_player,
        round=current_round,
    ).exists()
    if locked_player.balance_cents >= BAILOUT_BALANCE_LIMIT_CENTS and not lawn_job_started:
        raise BailoutError(
            "balance_too_high",
            "Track medic is only available below $10.",
        )

    prior = (
        BailoutSession.objects.select_related("race_entry__racer", "round")
        .prefetch_related("patches")
        .filter(player=locked_player, round=current_round)
        .first()
    )
    if prior is not None:
        raise BailoutError(
            "bailout_unavailable",
            "You already used track medic this round.",
        )

    entry_ids = list(
        RaceEntry.objects.filter(race__round=current_round)
        .order_by("lane")
        .values_list("pk", flat=True),
    )
    if not entry_ids:
        raise BailoutError("no_racers", "There are no racers in this round.")

    race_entry_id = pick_bailout_race_entry(
        player_id=locked_player.pk,
        round_id=current_round.pk,
        entry_ids=entry_ids,
    )
    race_entry = RaceEntry.objects.select_related("racer").get(pk=race_entry_id)
    wound_count, wounds = generate_bailout_wounds(
        player_id=locked_player.pk,
        round_id=current_round.pk,
        race_entry_id=race_entry.pk,
    )
    try:
        session = BailoutSession.objects.create(
            player=locked_player,
            round=current_round,
            race_entry=race_entry,
            start_request_id=client_request_id,
            wound_count=wound_count,
            wounds=wounds,
        )
    except IntegrityError as error:
        raise BailoutError(
            "bailout_unavailable",
            "You already used track medic this round.",
        ) from error
    return _serialize_session(
        session,
        patched_indices=[],
        balance_cents=locked_player.balance_cents,
    )


@transaction.atomic
def patch_bailout_wound(
    *,
    player: Player,
    session_id: int,
    wound_index: int,
    client_request_id: uuid.UUID,
) -> BailoutPatchReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        BailoutPatch.objects.select_related(
            "session__race_entry__racer",
            "session__round",
        ).filter(session__player=locked_player, patch_request_id=client_request_id),
        lambda patch: _serialize_patch(
            patch.session,
            wound_index=patch.wound_index,
            patched_indices=_patched_indices(patch.session),
            balance_cents=locked_player.balance_cents,
            duplicate=True,
        ),
    )
    if duplicate is not None:
        return duplicate

    try:
        session = (
            BailoutSession.objects.select_for_update()
            .select_related("race_entry__racer", "round")
            .get(pk=session_id, player=locked_player)
        )
    except BailoutSession.DoesNotExist as error:
        raise BailoutError("unknown_session", "That track medic session was not found.") from error

    current_round = _current_or_show_round(session.round_id)
    if current_round is None:
        raise BailoutError(
            "stale_session",
            "That track medic session belongs to a previous round.",
        )

    if session.completed_at is not None:
        raise BailoutError(
            "bailout_completed",
            "That track medic session is already complete.",
        )

    if wound_index < 0 or wound_index >= session.wound_count:
        raise BailoutError("invalid_wound_index", "That wound does not exist.")

    if session.patches.filter(wound_index=wound_index).exists():
        raise BailoutError("wound_already_patched", "That wound is already patched.")

    try:
        patch, duplicate_created = create_idempotently(
            create=lambda: BailoutPatch.objects.create(
                session=session,
                wound_index=wound_index,
                patch_request_id=client_request_id,
            ),
            duplicate_queryset=lambda: BailoutPatch.objects.filter(
                session=session,
                patch_request_id=client_request_id,
            ),
        )
    except IntegrityError as error:
        raise BailoutError(
            "wound_already_patched",
            "That wound is already patched.",
        ) from error
    if duplicate_created:
        session.refresh_from_db()
        locked_player.refresh_from_db()
        return _serialize_patch(
            session,
            wound_index=patch.wound_index,
            patched_indices=_patched_indices(session),
            balance_cents=locked_player.balance_cents,
            duplicate=True,
        )
    _maybe_complete_session(session=session, locked_player=locked_player)
    session.refresh_from_db()
    return _serialize_patch(
        session,
        wound_index=wound_index,
        patched_indices=_patched_indices(session),
        balance_cents=locked_player.balance_cents,
    )


def serialize_track_medic(
    *,
    player: Player,
    current_round: Round | None,
) -> dict[str, object]:
    if current_round is None:
        return {"eligible": False, "session": None, "stale": False}

    session = (
        BailoutSession.objects.select_related("race_entry__racer", "round")
        .prefetch_related("patches")
        .filter(player=player, round=current_round)
        .first()
    )
    if session is not None:
        patched = _patched_indices(session)
        completed = session.completed_at is not None
        return {
            "eligible": not completed,
            "session": {
                "id": session.pk,
                "round_id": session.round_id,
                "completed": completed,
                "target": {
                    "race_entry_id": session.race_entry_id,
                    "racer_id": session.race_entry.racer_id,
                    "racer_name": session.race_entry.racer.name,
                    "sprite_key": session.race_entry.racer.sprite_key,
                    "portrait_url": (
                        f"/static/assets/racers/portraits/{session.race_entry.racer.sprite_key}.png"
                    ),
                },
                "wounds": [
                    {
                        "index": index,
                        "x": wound["x"],
                        "y": wound["y"],
                        "patched": index in patched,
                    }
                    for index, wound in enumerate(session.wounds)
                ],
                "patched_count": len(patched),
                "wound_count": session.wound_count,
                "reward_cents": BAILOUT_REWARD_CENTS,
            },
            "stale": False,
        }

    return {
        "eligible": (
            player.balance_cents < BAILOUT_BALANCE_LIMIT_CENTS
            or LawnMowingSession.objects.filter(player=player, round=current_round).exists()
        ),
        "session": None,
        "stale": False,
    }
