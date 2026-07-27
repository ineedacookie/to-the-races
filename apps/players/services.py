from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.betting.models import LedgerEntry
from apps.players.avatar import normalize_avatar_recipe
from apps.players.models import Device, Player
from apps.players.names import random_nickname
from apps.racing.models import RoomSettings


class PlayerLoginError(Exception):
    pass


def available_random_nickname() -> str:
    for _attempt in range(100):
        candidate = random_nickname()
        if not Player.objects.filter(nickname__iexact=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate an available nickname.")


@transaction.atomic
def create_player(
    device: Device,
    requested_nickname: str | None = None,
    avatar_recipe: object | None = None,
) -> Player:
    locked_device = Device.objects.select_for_update().select_related("player").get(pk=device.pk)
    existing = locked_device.player
    if existing is not None:
        return existing

    room = RoomSettings.load()
    nickname = requested_nickname.strip() if requested_nickname else available_random_nickname()
    player = Player(
        nickname=nickname,
        avatar_recipe=normalize_avatar_recipe(
            avatar_recipe,
            seed=locked_device.token.int,
        ),
        balance_cents=room.opening_balance_cents,
    )
    try:
        player.full_clean()
        player.save()
    except IntegrityError as error:
        raise ValidationError({"nickname": "That nickname is already racing."}) from error

    locked_device.player = player
    locked_device.save(update_fields=["player", "last_seen_at"])
    LedgerEntry.objects.create(
        player=player,
        kind=LedgerEntry.Kind.OPENING,
        amount_cents=room.opening_balance_cents,
        balance_after_cents=room.opening_balance_cents,
        description="Opening fun-money balance",
    )
    return player


@transaction.atomic
def login_player(device: Device, nickname: str) -> Player:
    normalized_nickname = " ".join(nickname.split()).strip()
    if not normalized_nickname:
        raise PlayerLoginError("Enter an existing username.")

    locked_device = Device.objects.select_for_update().get(pk=device.pk)
    player = (
        Player.objects.select_for_update()
        .filter(nickname__iexact=normalized_nickname)
        .first()
    )
    if player is None:
        raise PlayerLoginError("No racer has that username yet.")

    locked_device.player = player
    locked_device.save(update_fields=["player", "last_seen_at"])
    return player


@transaction.atomic
def rename_player(player: Player, nickname: str) -> Player:
    return update_player_identity(player, nickname=nickname)


@transaction.atomic
def update_player_identity(
    player: Player,
    *,
    nickname: str | None = None,
    avatar_recipe: object | None = None,
) -> Player:
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    update_fields = ["updated_at"]
    if nickname is not None:
        locked_player.nickname = nickname
        update_fields.append("nickname")
    if avatar_recipe is not None:
        locked_player.avatar_recipe = normalize_avatar_recipe(
            avatar_recipe,
            seed=locked_player.pk,
        )
        update_fields.append("avatar_recipe")
    try:
        locked_player.full_clean()
        locked_player.save(update_fields=update_fields)
    except IntegrityError as error:
        raise ValidationError({"nickname": "That nickname is already racing."}) from error
    return locked_player
