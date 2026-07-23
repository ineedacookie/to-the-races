from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.betting.models import LedgerEntry
from apps.players.models import Device, Player
from apps.players.names import random_nickname
from apps.racing.models import RoomSettings


def available_random_nickname() -> str:
    for _attempt in range(100):
        candidate = random_nickname()
        if not Player.objects.filter(nickname__iexact=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate an available nickname.")


@transaction.atomic
def create_player(device: Device, requested_nickname: str | None = None) -> Player:
    locked_device = Device.objects.select_for_update().get(pk=device.pk)
    existing = Player.objects.filter(device=locked_device).first()
    if existing is not None:
        return existing

    room = RoomSettings.load()
    nickname = requested_nickname.strip() if requested_nickname else available_random_nickname()
    player = Player(
        device=locked_device,
        nickname=nickname,
        balance_cents=room.opening_balance_cents,
    )
    try:
        player.full_clean()
        player.save()
    except IntegrityError as error:
        raise ValidationError({"nickname": "That nickname is already racing."}) from error

    LedgerEntry.objects.create(
        player=player,
        kind=LedgerEntry.Kind.OPENING,
        amount_cents=room.opening_balance_cents,
        balance_after_cents=room.opening_balance_cents,
        description="Opening fun-money balance",
    )
    return player


@transaction.atomic
def rename_player(player: Player, nickname: str) -> Player:
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    locked_player.nickname = nickname
    try:
        locked_player.full_clean()
        locked_player.save(update_fields=["nickname", "updated_at"])
    except IntegrityError as error:
        raise ValidationError({"nickname": "That nickname is already racing."}) from error
    return locked_player
