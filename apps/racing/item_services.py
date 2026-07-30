from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.betting.models import LedgerEntry
from apps.betting.money import available_funds_message, remaining_budget_message
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.core.idempotency import existing_receipt
from apps.players.models import Player
from apps.racing.models import (
    InventoryItem,
    ItemDefinition,
    RaceEntry,
    RoomSettings,
    Round,
    RoundDiscount,
    RoundItemUse,
)
from apps.racing.round_guards import (
    latest_round,
    locked_round,
    require_betting_open,
    require_live_race,
)
from apps.racing.upgrade_services import effective_inventory_capacity


class ItemActionError(ServiceError):
    pass


@dataclass(frozen=True, slots=True)
class ItemPurchaseReceipt:
    inventory_item_id: int
    balance_cents: int
    item_name: str
    price_paid_cents: int
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class ItemDiscardReceipt:
    inventory_item_id: int
    item_name: str
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class ItemUseReceipt:
    use_id: int
    inventory_item_id: int
    balance_cents: int
    item_name: str
    price_paid_cents: int
    live_activation: bool
    duplicate: bool = False


def _is_potion(item: ItemDefinition) -> bool:
    return item.target == ItemDefinition.Target.RACER


def _purchase_receipt(
    inventory_item: InventoryItem,
    balance_cents: int,
    *,
    duplicate: bool = False,
) -> ItemPurchaseReceipt:
    return ItemPurchaseReceipt(
        inventory_item_id=inventory_item.pk,
        balance_cents=balance_cents,
        item_name=inventory_item.item.name,
        price_paid_cents=inventory_item.price_paid_cents,
        duplicate=duplicate,
    )


def _use_receipt(
    use: RoundItemUse,
    balance_cents: int,
    *,
    duplicate: bool = False,
) -> ItemUseReceipt:
    if use.inventory_item_id is None:
        raise RuntimeError("Inventory-backed item use is missing its inventory item.")
    return ItemUseReceipt(
        use_id=use.pk,
        inventory_item_id=use.inventory_item_id,
        balance_cents=balance_cents,
        item_name=use.item.name,
        price_paid_cents=use.price_paid_cents,
        live_activation=not _is_potion(use.item),
        duplicate=duplicate,
    )


def _live_item_placement(
    *,
    current_round: Round,
    target_entry: RaceEntry,
    now: datetime,
) -> tuple[int, float, float]:
    race = current_round.race
    if race.seed is None or not race.timeline:
        raise ItemActionError("race_not_ready", "The live race is not ready for items yet.")
    elapsed_seconds = max((now - current_round.race_starts_at).total_seconds(), 0.0)
    current_tick = min(int(elapsed_seconds * race.tick_rate), race.duration_ticks)
    arm_delay_ticks = max(round(0.25 * race.tick_rate), 1)
    activation_tick = min(current_tick + arm_delay_ticks, race.duration_ticks)
    if activation_tick <= current_tick:
        raise ItemActionError("item_too_late", "The race ended before that item could arm.")
    frames: list[dict[str, Any]] = race.timeline
    frame = max(
        (candidate for candidate in frames if int(candidate.get("tick", 0)) <= current_tick),
        key=lambda candidate: int(candidate.get("tick", 0)),
        default=frames[0],
    )
    racer_frame = next(
        (
            candidate
            for candidate in frame.get("racers", [])
            if int(candidate.get("id", 0)) == target_entry.racer_id
        ),
        None,
    )
    if racer_frame is None or racer_frame.get("state") in {
        "finished",
        "knocked_out",
        "destroyed",
        "dnf",
    }:
        raise ItemActionError(
            "racer_unavailable",
            "That racer is already out. Pick someone still racing.",
        )
    racer_x = float(racer_frame.get("x", 0.0))
    if racer_x >= 0.90:
        raise ItemActionError(
            "item_too_late",
            "That racer is too close to the finish line for a live item.",
        )
    track_lane = float(racer_frame.get("y", target_entry.lane))
    track_position = min(max(racer_x + 0.08, 0.20), 0.925)
    return activation_tick, track_lane, track_position


@transaction.atomic
def purchase_item(
    *,
    player: Player,
    item_slug: str,
    client_request_id: uuid.UUID,
) -> ItemPurchaseReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        InventoryItem.objects.select_related("item").filter(
            player=locked_player,
            purchase_request_id=client_request_id,
        ),
        lambda item: _purchase_receipt(item, locked_player.balance_cents, duplicate=True),
    )
    if duplicate is not None:
        return duplicate

    try:
        item = ItemDefinition.objects.get(slug=item_slug, active=True)
    except ItemDefinition.DoesNotExist as error:
        raise ItemActionError("unknown_item", "That item is not available.") from error

    room = RoomSettings.load()
    inventory_limit = effective_inventory_capacity(player=locked_player, room=room)
    inventory_count = InventoryItem.objects.filter(
        player=locked_player,
        used_at__isnull=True,
        discarded_at__isnull=True,
    ).count()
    if inventory_count >= inventory_limit:
        raise ItemActionError(
            "inventory_full",
            f"Your bag is full. You may carry up to {inventory_limit} items.",
        )

    current_round = latest_round()
    price_cents = item.price_cents
    if current_round is not None:
        discount = (
            RoundDiscount.objects.filter(round=current_round, item=item).values_list(
                "discount_pct",
                flat=True,
            )
        ).first()
        if discount is not None:
            price_cents = item.price_cents * (100 - discount) // 100

    inventory_item = InventoryItem.objects.create(
        player=locked_player,
        item=item,
        price_paid_cents=price_cents,
        purchase_request_id=client_request_id,
    )
    change_balance(
        player=locked_player,
        current_round=current_round,
        kind=LedgerEntry.Kind.ITEM,
        amount_cents=-price_cents,
        description=f"Bought {item.name}",
        error_type=ItemActionError,
        insufficient_message=available_funds_message(price_cents),
    )
    return _purchase_receipt(inventory_item, locked_player.balance_cents)


@transaction.atomic
def discard_inventory_item(
    *,
    player: Player,
    inventory_item_id: int,
) -> ItemDiscardReceipt:
    try:
        inventory_item = (
            InventoryItem.objects.select_for_update()
            .select_related("item")
            .get(pk=inventory_item_id, player_id=player.pk)
        )
    except InventoryItem.DoesNotExist as error:
        raise ItemActionError("unknown_inventory_item", "That item is not in your bag.") from error
    if inventory_item.used_at is not None:
        raise ItemActionError("item_already_used", "That item has already been used.")
    if inventory_item.discarded_at is not None:
        return ItemDiscardReceipt(
            inventory_item_id=inventory_item.pk,
            item_name=inventory_item.item.name,
            duplicate=True,
        )

    inventory_item.discarded_at = timezone.now()
    inventory_item.save(update_fields=["discarded_at"])
    return ItemDiscardReceipt(
        inventory_item_id=inventory_item.pk,
        item_name=inventory_item.item.name,
    )


@transaction.atomic
def use_inventory_item(
    *,
    player: Player,
    round_id: int,
    inventory_item_id: int,
    client_request_id: uuid.UUID,
    target_entry_id: int,
) -> ItemUseReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        RoundItemUse.objects.select_related("item", "inventory_item").filter(
            player=locked_player,
            client_request_id=client_request_id,
        ),
        lambda use: _use_receipt(use, locked_player.balance_cents, duplicate=True),
    )
    if duplicate is not None:
        return duplicate

    try:
        inventory_item = (
            InventoryItem.objects.select_for_update()
            .select_related("item")
            .get(pk=inventory_item_id, player=locked_player)
        )
    except InventoryItem.DoesNotExist as error:
        raise ItemActionError("unknown_inventory_item", "That item is not in your bag.") from error
    if inventory_item.used_at is not None:
        raise ItemActionError("item_already_used", "That item has already been used.")
    if inventory_item.discarded_at is not None:
        raise ItemActionError("item_discarded", "That item was thrown away.")

    current_round = locked_round(round_id, error_type=ItemActionError, select_race=True)

    now = timezone.now()
    item = inventory_item.item
    is_potion = _is_potion(item)
    room = RoomSettings.load()
    if is_potion:
        require_betting_open(
            current_round=current_round,
            room=room,
            error_type=ItemActionError,
            code="potion_window_closed",
            message="Potions must be assigned before betting closes.",
            now=now,
        )
    else:
        require_live_race(
            current_round=current_round,
            room=room,
            error_type=ItemActionError,
            message="Track items can only be used while the race is live.",
            now=now,
        )

    use_count = RoundItemUse.objects.filter(player=locked_player, round=current_round).count()
    if use_count >= room.max_round_item_uses:
        raise ItemActionError(
            "item_use_cap",
            f"You may deploy at most {room.max_round_item_uses} items per round.",
        )

    spent = (
        RoundItemUse.objects.filter(player=locked_player, round=current_round)
        .aggregate(total=Sum("price_paid_cents"))
        .get("total")
        or 0
    )
    if spent + inventory_item.price_paid_cents > room.max_round_item_spend_cents:
        remaining = max(room.max_round_item_spend_cents - spent, 0)
        raise ItemActionError(
            "item_spend_cap",
            "That exceeds this round's item budget. "
            + remaining_budget_message(remaining),
        )

    try:
        target_entry = RaceEntry.objects.select_related("racer").get(
            pk=target_entry_id,
            race=current_round.race,
        )
    except RaceEntry.DoesNotExist as error:
        raise ItemActionError(
            "unknown_racer",
            "Choose one of the four racers in this round.",
        ) from error

    track_lane: float | None = None
    track_position: float | None = None
    activation_tick = 0
    if not is_potion:
        if item.target != ItemDefinition.Target.TRACK:
            raise ItemActionError("invalid_item", "That live item is missing track targeting.")
        activation_tick, track_lane, track_position = _live_item_placement(
            current_round=current_round,
            target_entry=target_entry,
            now=now,
        )

    use = RoundItemUse.objects.create(
        player=locked_player,
        round=current_round,
        item=item,
        inventory_item=inventory_item,
        target_entry=target_entry,
        track_lane=track_lane,
        track_position=track_position,
        activation_tick=activation_tick,
        price_paid_cents=inventory_item.price_paid_cents,
        client_request_id=client_request_id,
    )
    inventory_item.used_at = timezone.now()
    inventory_item.save(update_fields=["used_at"])
    return _use_receipt(use, locked_player.balance_cents)
