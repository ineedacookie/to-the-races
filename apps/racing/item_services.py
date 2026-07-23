from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.betting.models import LedgerEntry
from apps.players.models import Player
from apps.racing.models import ItemDefinition, RaceEntry, RoomSettings, Round, RoundItemUse


class ItemDeployError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ItemDeployReceipt:
    use_id: int
    balance_cents: int
    item_name: str
    price_paid_cents: int
    duplicate: bool = False


def _receipt(
    use: RoundItemUse,
    balance_cents: int,
    *,
    duplicate: bool = False,
) -> ItemDeployReceipt:
    return ItemDeployReceipt(
        use_id=use.pk,
        balance_cents=balance_cents,
        item_name=use.item.name,
        price_paid_cents=use.price_paid_cents,
        duplicate=duplicate,
    )


def _validate_track_coordinates(
    *,
    track_lane: float,
    track_position: float,
    lane_count: int,
) -> None:
    valid_lanes = [lane / (lane_count + 1) for lane in range(1, lane_count + 1)]
    if not any(abs(track_lane - valid_lane) < 0.001 for valid_lane in valid_lanes):
        raise ItemDeployError("invalid_target", "Choose one of this round's track lanes.")
    if not 0.2 <= track_position <= 0.85:
        raise ItemDeployError("invalid_target", "Track position must be between 0.2 and 0.85.")


@transaction.atomic
def deploy_item(
    *,
    player: Player,
    round_id: int,
    item_slug: str,
    client_request_id: uuid.UUID,
    target_entry_id: int | None = None,
    track_lane: float | None = None,
    track_position: float | None = None,
) -> ItemDeployReceipt:
    locked_player = Player.objects.select_for_update().get(pk=player.pk)
    existing = (
        RoundItemUse.objects.select_related("item")
        .filter(player=locked_player, client_request_id=client_request_id)
        .first()
    )
    if existing is not None:
        return _receipt(existing, locked_player.balance_cents, duplicate=True)

    try:
        current_round = Round.objects.select_for_update().select_related("race").get(pk=round_id)
    except Round.DoesNotExist as error:
        raise ItemDeployError("unknown_round", "That round is not active.") from error

    if current_round.state != Round.State.OPEN or timezone.now() >= current_round.locks_at:
        raise ItemDeployError("betting_closed", "Items can only be deployed while betting is open.")

    try:
        item = ItemDefinition.objects.get(slug=item_slug, active=True)
    except ItemDefinition.DoesNotExist as error:
        raise ItemDeployError("unknown_item", "That item is not available.") from error

    if locked_player.balance_cents < item.price_cents:
        raise ItemDeployError(
            "insufficient_funds",
            f"You need {item.price_cents // 100} dollars in available fun money.",
        )

    if RoundItemUse.objects.filter(player=locked_player, round=current_round, item=item).exists():
        raise ItemDeployError("item_already_used", "You already deployed that item this round.")

    room = RoomSettings.load()
    use_count = RoundItemUse.objects.filter(player=locked_player, round=current_round).count()
    if use_count >= room.max_round_item_uses:
        raise ItemDeployError(
            "item_use_cap",
            f"You may deploy at most {room.max_round_item_uses} items per round.",
        )

    spent = (
        RoundItemUse.objects.filter(player=locked_player, round=current_round)
        .aggregate(total=Sum("price_paid_cents"))
        .get("total")
        or 0
    )
    if spent + item.price_cents > room.max_round_item_spend_cents:
        remaining = max(room.max_round_item_spend_cents - spent, 0)
        raise ItemDeployError(
            "item_spend_cap",
            (
                "That exceeds this round's item budget. "
                f"You may still spend {remaining // 100} dollars."
            ),
        )

    target_entry: RaceEntry | None = None
    if item.target == ItemDefinition.Target.RACER:
        if target_entry_id is None:
            raise ItemDeployError("invalid_target", "Racer items require a target entry.")
        try:
            target_entry = RaceEntry.objects.select_related("racer").get(
                pk=target_entry_id,
                race=current_round.race,
            )
        except RaceEntry.DoesNotExist as error:
            raise ItemDeployError(
                "unknown_racer",
                "That racer is not in this round.",
            ) from error
        if track_lane is not None or track_position is not None:
            raise ItemDeployError("invalid_target", "Racer items cannot set track coordinates.")
    else:
        if target_entry_id is not None:
            raise ItemDeployError("invalid_target", "Track items cannot target a racer entry.")
        if track_lane is None or track_position is None:
            raise ItemDeployError("invalid_target", "Track items require lane and position.")
        _validate_track_coordinates(
            track_lane=track_lane,
            track_position=track_position,
            lane_count=current_round.race.entries.count(),
        )

    use = RoundItemUse.objects.create(
        player=locked_player,
        round=current_round,
        item=item,
        target_entry=target_entry,
        track_lane=track_lane,
        track_position=track_position,
        price_paid_cents=item.price_cents,
        client_request_id=client_request_id,
    )
    locked_player.balance_cents -= item.price_cents
    locked_player.save(update_fields=["balance_cents", "updated_at"])
    LedgerEntry.objects.create(
        player=locked_player,
        round=current_round,
        kind=LedgerEntry.Kind.ITEM,
        amount_cents=-item.price_cents,
        balance_after_cents=locked_player.balance_cents,
        description=f"Deployed {item.name}",
    )
    return _receipt(use, locked_player.balance_cents)
