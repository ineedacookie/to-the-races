from __future__ import annotations

from datetime import datetime

from django.db.models import QuerySet
from django.utils import timezone

from apps.core.errors import ServiceError
from apps.racing.models import RoomSettings, Round


def latest_round(*, for_update: bool = False, select_race: bool = False) -> Round | None:
    rounds: QuerySet[Round] = Round.objects.all()
    if for_update:
        rounds = rounds.select_for_update()
    if select_race:
        rounds = rounds.select_related("race")
    return rounds.order_by("-number").first()


def locked_round(
    round_id: int,
    *,
    error_type: type[ServiceError],
    select_race: bool = False,
) -> Round:
    rounds = Round.objects.select_for_update()
    if select_race:
        rounds = rounds.select_related("race")
    try:
        return rounds.get(pk=round_id)
    except Round.DoesNotExist as error:
        raise error_type("unknown_round", "That round is not active.") from error


def betting_is_open(
    *,
    current_round: Round,
    room: RoomSettings,
    now: datetime | None = None,
) -> bool:
    current_time = now or timezone.now()
    return (
        current_round.state == Round.State.OPEN
        and not room.is_paused
        and current_time < current_round.locks_at
    )


def require_betting_open(
    *,
    current_round: Round,
    room: RoomSettings,
    error_type: type[ServiceError],
    message: str,
    code: str = "betting_closed",
    now: datetime | None = None,
) -> None:
    if not betting_is_open(current_round=current_round, room=room, now=now):
        raise error_type(code, message)


def require_live_race(
    *,
    current_round: Round,
    room: RoomSettings,
    error_type: type[ServiceError],
    message: str,
    now: datetime | None = None,
) -> None:
    current_time = now or timezone.now()
    if (
        current_round.state != Round.State.RACING
        or room.is_paused
        or current_time >= current_round.race_ends_at
    ):
        raise error_type("live_item_window_closed", message)
