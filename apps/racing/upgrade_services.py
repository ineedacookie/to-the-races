from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.betting.models import LedgerEntry
from apps.betting.money import available_funds_message
from apps.betting.wallet import change_balance, lock_player
from apps.core.errors import ServiceError
from apps.core.idempotency import create_idempotently, existing_receipt
from apps.players.models import Player
from apps.racing.models import PlayerUpgrade, RoomSettings, UpgradeDefinition
from apps.racing.round_guards import latest_round


class UpgradePurchaseError(ServiceError):
    pass


@dataclass(frozen=True, slots=True)
class UpgradePurchaseReceipt:
    player_upgrade_id: int
    balance_cents: int
    upgrade_name: str
    inventory_capacity: int | None
    price_paid_cents: int
    duplicate: bool = False


def _receipt(
    player_upgrade: PlayerUpgrade,
    balance_cents: int,
    *,
    duplicate: bool = False,
) -> UpgradePurchaseReceipt:
    return UpgradePurchaseReceipt(
        player_upgrade_id=player_upgrade.pk,
        balance_cents=balance_cents,
        upgrade_name=player_upgrade.upgrade.name,
        inventory_capacity=player_upgrade.upgrade.inventory_capacity,
        price_paid_cents=player_upgrade.price_paid_cents,
        duplicate=duplicate,
    )


def _owned_upgrade_slugs(*, player: Player) -> set[str]:
    return set(
        PlayerUpgrade.objects.filter(player=player)
        .values_list("upgrade__slug", flat=True)
    )


def effective_inventory_capacity(
    *,
    player: Player,
    room: RoomSettings | None = None,
    owned_capacities: Iterable[int | None] | None = None,
) -> int:
    room = room or RoomSettings.load()
    if owned_capacities is None:
        owned_capacities = PlayerUpgrade.objects.filter(
            player=player,
            upgrade__kind=UpgradeDefinition.Kind.INVENTORY_CAPACITY,
            upgrade__inventory_capacity__isnull=False,
        ).values_list("upgrade__inventory_capacity", flat=True)
    capacities = [capacity for capacity in owned_capacities if capacity is not None]
    if not capacities:
        return room.max_inventory_items
    return max(room.max_inventory_items, max(capacities))


def next_inventory_upgrade(
    *,
    player: Player,
    catalog: list[UpgradeDefinition] | None = None,
    owned_slugs: set[str] | None = None,
) -> UpgradeDefinition | None:
    if catalog is None:
        catalog = list(
            UpgradeDefinition.objects.filter(
                active=True,
                kind=UpgradeDefinition.Kind.INVENTORY_CAPACITY,
            ).order_by("sort_order", "name")
        )
    owned = owned_slugs if owned_slugs is not None else _owned_upgrade_slugs(player=player)
    for upgrade in catalog:
        if upgrade.kind != UpgradeDefinition.Kind.INVENTORY_CAPACITY:
            continue
        if upgrade.slug in owned:
            continue
        prerequisite = upgrade.prerequisite
        if prerequisite is not None and prerequisite.slug not in owned:
            continue
        return upgrade
    return None


@transaction.atomic
def purchase_upgrade(
    *,
    player: Player,
    upgrade_slug: str,
    client_request_id: uuid.UUID,
) -> UpgradePurchaseReceipt:
    locked_player = lock_player(player)
    duplicate = existing_receipt(
        PlayerUpgrade.objects.select_related("upgrade").filter(
            player=locked_player,
            purchase_request_id=client_request_id,
        ),
        lambda upgrade: _receipt(upgrade, locked_player.balance_cents, duplicate=True),
    )
    if duplicate is not None:
        return duplicate

    try:
        upgrade = UpgradeDefinition.objects.select_related("prerequisite").get(
            slug=upgrade_slug,
            active=True,
        )
    except UpgradeDefinition.DoesNotExist as error:
        raise UpgradePurchaseError(
            "unknown_upgrade",
            "That upgrade is not available.",
        ) from error

    if PlayerUpgrade.objects.filter(player=locked_player, upgrade=upgrade).exists():
        raise UpgradePurchaseError(
            "upgrade_already_owned",
            f"You already own {upgrade.name}.",
        )

    if upgrade.prerequisite_id is not None:
        prerequisite = upgrade.prerequisite
        assert prerequisite is not None
        has_prerequisite = PlayerUpgrade.objects.filter(
            player=locked_player,
            upgrade=prerequisite,
        ).exists()
        if not has_prerequisite:
            raise UpgradePurchaseError(
                "upgrade_prerequisite_missing",
                f"Buy {prerequisite.name} first.",
            )

    try:
        player_upgrade, duplicate_created = create_idempotently(
            create=lambda: PlayerUpgrade.objects.create(
                player=locked_player,
                upgrade=upgrade,
                price_paid_cents=upgrade.price_cents,
                purchase_request_id=client_request_id,
            ),
            duplicate_queryset=lambda: PlayerUpgrade.objects.select_related("upgrade").filter(
                player=locked_player,
                purchase_request_id=client_request_id,
            ),
        )
    except IntegrityError as error:
        raise UpgradePurchaseError(
            "upgrade_already_owned",
            f"You already own {upgrade.name}.",
        ) from error
    if duplicate_created:
        return _receipt(player_upgrade, locked_player.balance_cents, duplicate=True)

    change_balance(
        player=locked_player,
        current_round=latest_round(),
        kind=LedgerEntry.Kind.UPGRADE,
        amount_cents=-upgrade.price_cents,
        description=f"Bought {upgrade.name}",
        error_type=UpgradePurchaseError,
        insufficient_message=available_funds_message(upgrade.price_cents),
    )
    return _receipt(player_upgrade, locked_player.balance_cents)
