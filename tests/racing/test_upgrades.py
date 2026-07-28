from __future__ import annotations

import json
import uuid

import pytest
from apps.betting.models import LedgerEntry
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import advance_once
from apps.racing.item_services import ItemActionError, purchase_item
from apps.racing.management.commands.seed_game import CANONICAL_SLUGS
from apps.racing.models import (
    InventoryItem,
    PlayerUpgrade,
    RaceEntry,
    Racer,
    RoomSettings,
    Round,
    UpgradeDefinition,
)
from apps.racing.serializers import build_live_state
from apps.racing.upgrade_services import (
    UpgradePurchaseError,
    effective_inventory_capacity,
    next_inventory_upgrade,
    purchase_upgrade,
)
from django.test import Client
from django.utils import timezone
from tests.factories import (
    open_round_with_entries as create_open_round_with_entries,
)
from tests.factories import (
    seed_catalog,
)

pytestmark = pytest.mark.django_db

def open_round_with_entries() -> tuple[Round, RaceEntry, RaceEntry]:
    return create_open_round_with_entries(
        use_catalog=True,
    )


def test_seed_game_creates_inventory_upgrade_tiers() -> None:
    seed_catalog()

    upgrades = list(UpgradeDefinition.objects.filter(active=True).order_by("sort_order", "name"))
    assert len(upgrades) == 2
    assert upgrades[0].slug == "expanded-pockets"
    assert upgrades[0].inventory_capacity == 6
    assert upgrades[0].price_cents == 15_000
    assert upgrades[0].prerequisite_id is None
    assert upgrades[1].slug == "deep-pockets"
    assert upgrades[1].inventory_capacity == 8
    assert upgrades[1].price_cents == 35_000
    assert upgrades[1].prerequisite_id == upgrades[0].pk


def test_effective_inventory_capacity_uses_room_baseline_or_highest_owned_tier() -> None:
    seed_catalog()
    player = create_player(Device.objects.create(), "Capacity Fan")
    room = RoomSettings.load()

    assert effective_inventory_capacity(player=player, room=room) == room.max_inventory_items

    tier_one = UpgradeDefinition.objects.get(slug="expanded-pockets")
    PlayerUpgrade.objects.create(
        player=player,
        upgrade=tier_one,
        price_paid_cents=tier_one.price_cents,
    )
    assert effective_inventory_capacity(player=player, room=room) == 6

    tier_two = UpgradeDefinition.objects.get(slug="deep-pockets")
    PlayerUpgrade.objects.create(
        player=player,
        upgrade=tier_two,
        price_paid_cents=tier_two.price_cents,
    )
    assert effective_inventory_capacity(player=player, room=room) == 8
    UpgradeDefinition.objects.filter(pk__in=[tier_one.pk, tier_two.pk]).update(active=False)
    assert effective_inventory_capacity(player=player, room=room) == 8


def test_upgrade_purchase_is_idempotent_and_records_ledger() -> None:
    open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 50_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Upgrade Fan")
    request_id = uuid.uuid4()
    opening_balance = player.balance_cents

    original = purchase_upgrade(
        player=player,
        upgrade_slug="expanded-pockets",
        client_request_id=request_id,
    )
    duplicate = purchase_upgrade(
        player=player,
        upgrade_slug="expanded-pockets",
        client_request_id=request_id,
    )

    player.refresh_from_db()
    assert original.player_upgrade_id == duplicate.player_upgrade_id
    assert duplicate.duplicate is True
    assert player.balance_cents == opening_balance - 15_000
    assert PlayerUpgrade.objects.filter(player=player).count() == 1
    assert (
        LedgerEntry.objects.filter(
            player=player,
            kind=LedgerEntry.Kind.UPGRADE,
        ).count()
        == 1
    )


def test_upgrade_purchase_rejects_duplicate_ownership_prerequisite_and_funds() -> None:
    open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 50_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Upgrade Guard")

    purchase_upgrade(
        player=player,
        upgrade_slug="expanded-pockets",
        client_request_id=uuid.uuid4(),
    )

    with pytest.raises(UpgradePurchaseError) as caught:
        purchase_upgrade(
            player=player,
            upgrade_slug="expanded-pockets",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "upgrade_already_owned"

    fresh_player = create_player(Device.objects.create(), "Needs Tier One")
    with pytest.raises(UpgradePurchaseError) as caught:
        purchase_upgrade(
            player=fresh_player,
            upgrade_slug="deep-pockets",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "upgrade_prerequisite_missing"

    poor_player = create_player(Device.objects.create(), "Broke Fan")
    poor_player.balance_cents = 5_000
    poor_player.save(update_fields=["balance_cents", "updated_at"])
    with pytest.raises(UpgradePurchaseError) as caught:
        purchase_upgrade(
            player=poor_player,
            upgrade_slug="expanded-pockets",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "insufficient_funds"

    inactive = UpgradeDefinition.objects.get(slug="deep-pockets")
    inactive.active = False
    inactive.save(update_fields=["active"])
    with pytest.raises(UpgradePurchaseError) as caught:
        purchase_upgrade(
            player=player,
            upgrade_slug="deep-pockets",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "unknown_upgrade"


def test_both_inventory_tiers_raise_item_capacity_and_next_upgrade() -> None:
    open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 100_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Bag Expander")

    next_upgrade = next_inventory_upgrade(player=player)
    assert next_upgrade is not None
    assert next_upgrade.slug == "expanded-pockets"

    purchase_upgrade(
        player=player,
        upgrade_slug="expanded-pockets",
        client_request_id=uuid.uuid4(),
    )
    assert effective_inventory_capacity(player=player) == 6
    next_upgrade = next_inventory_upgrade(player=player)
    assert next_upgrade is not None
    assert next_upgrade.slug == "deep-pockets"

    for slug in (
        "quantum-quencher",
        "rubber-bone-broth",
        "potion-of-minor-inconvenience",
        "null-pointer-nectar",
        "maximum-ooze",
        "fun-size-fizz",
    ):
        purchase_item(
            player=player,
            item_slug=slug,
            client_request_id=uuid.uuid4(),
        )
    assert (
        InventoryItem.objects.filter(
            player=player,
            used_at__isnull=True,
            discarded_at__isnull=True,
        ).count()
        == 6
    )

    with pytest.raises(ItemActionError) as caught:
        purchase_item(
            player=player,
            item_slug="identity-crisis-cordial",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "inventory_full"

    purchase_upgrade(
        player=player,
        upgrade_slug="deep-pockets",
        client_request_id=uuid.uuid4(),
    )
    assert effective_inventory_capacity(player=player) == 8
    assert next_inventory_upgrade(player=player) is None

    purchase_item(
        player=player,
        item_slug="identity-crisis-cordial",
        client_request_id=uuid.uuid4(),
    )
    purchase_item(
        player=player,
        item_slug="banana-of-binding",
        client_request_id=uuid.uuid4(),
    )
    assert (
        InventoryItem.objects.filter(
            player=player,
            used_at__isnull=True,
            discarded_at__isnull=True,
        ).count()
        == 8
    )


def test_live_state_exposes_upgrade_catalog_and_capacity() -> None:
    open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 50_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Protocol Fan")
    purchase_upgrade(
        player=player,
        upgrade_slug="expanded-pockets",
        client_request_id=uuid.uuid4(),
    )

    live_state = build_live_state(player_id=player.pk)

    assert live_state["protocol_version"] == 14
    assert len(live_state["room"]["upgrade_catalog"]) == 2
    assert live_state["room"]["upgrade_catalog"][0]["slug"] == "expanded-pockets"
    assert live_state["room"]["upgrade_catalog"][1]["prerequisite_slug"] == "expanded-pockets"
    assert live_state["player"]["effective_inventory_capacity"] == 6
    assert live_state["player"]["owned_upgrades"][0]["slug"] == "expanded-pockets"
    assert live_state["player"]["next_inventory_upgrade"]["slug"] == "deep-pockets"


def test_upgrade_purchase_api_requires_identity_and_broadcasts_state() -> None:
    open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 50_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    client = Client()
    client.get("/bet/")
    client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Upgrade API"}),
        content_type="application/json",
    )

    response = client.post(
        "/api/upgrades/purchase/",
        data=json.dumps(
            {
                "upgrade_slug": "expanded-pockets",
                "client_request_id": str(uuid.uuid4()),
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["player_upgrade"]["upgrade_name"] == "Expanded Pockets"
    assert payload["player_upgrade"]["inventory_capacity"] == 6

    state = client.get("/api/state/").json()
    assert state["player"]["effective_inventory_capacity"] == 6
    assert state["player"]["owned_upgrades"][0]["slug"] == "expanded-pockets"


def test_upgrade_purchase_api_rejects_anonymous_requests() -> None:
    seed_catalog()
    client = Client()
    response = client.post(
        "/api/upgrades/purchase/",
        data=json.dumps(
            {
                "upgrade_slug": "expanded-pockets",
                "client_request_id": str(uuid.uuid4()),
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 401


def test_canonical_odds_account_for_outer_lane_fire_pit_exposure() -> None:
    seed_catalog()

    advance_once(timezone.now())
    entries = {
        entry.racer.name: entry
        for entry in RaceEntry.objects.select_related("racer").order_by("lane")
    }

    assert entries["Bonejamin"].lane == 1
    assert entries["Blinky"].lane == 4
    inner_odds = max(entries["Spore Score"].odds, entries["Gob Smack"].odds)
    assert entries["Bonejamin"].odds > inner_odds
    assert entries["Blinky"].odds > inner_odds
    assert {racer.slug for racer in Racer.objects.filter(active=True)} == CANONICAL_SLUGS
