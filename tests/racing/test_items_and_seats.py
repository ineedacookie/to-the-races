from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from apps.betting.models import LedgerEntry
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import advance_once, regenerate_live_race
from apps.racing.item_services import (
    ItemActionError,
    discard_inventory_item,
    purchase_item,
    use_inventory_item,
)
from apps.racing.management.commands.seed_game import CANONICAL_SLUGS
from apps.racing.models import (
    InventoryItem,
    ItemDefinition,
    Race,
    RaceEntry,
    Racer,
    RoomSettings,
    Round,
    RoundItemUse,
    SpectatorSeatDefinition,
)
from apps.racing.seat_services import SeatClaimError, claim_seat
from apps.racing.serializers import build_live_state
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.django_db


def seed_catalog() -> None:
    call_command("seed_game")


def open_round_with_entries() -> tuple[Round, RaceEntry, RaceEntry]:
    seed_catalog()
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(minutes=1),
        race_starts_at=now + timedelta(minutes=2),
        race_ends_at=now + timedelta(minutes=3),
        results_end_at=now + timedelta(minutes=4),
    )
    race = Race.objects.create(round=current_round)
    racers = list(Racer.objects.filter(active=True).order_by("sort_order")[:2])
    first = RaceEntry.objects.create(race=race, racer=racers[0], lane=1, odds="3.00")
    second = RaceEntry.objects.create(race=race, racer=racers[1], lane=2, odds="4.00")
    return current_round, first, second


def start_live_round(current_round: Round, *, elapsed_seconds: float = 2.0) -> Round:
    now = timezone.now()
    current_round.locks_at = now - timedelta(seconds=elapsed_seconds + 1)
    current_round.race_starts_at = now - timedelta(seconds=elapsed_seconds)
    current_round.save(update_fields=["locks_at", "race_starts_at"])
    advance_once(now)
    advance_once(now)
    current_round.refresh_from_db()
    assert current_round.state == Round.State.RACING
    return current_round


def test_seed_game_keeps_four_active_canonical_racers() -> None:
    for index in range(6):
        Racer.objects.create(
            name=f"Legacy {index}",
            slug=f"legacy-{index}",
            sprite_key=f"legacy-{index}",
            active=True,
        )

    call_command("seed_game")

    active = list(Racer.objects.filter(active=True).order_by("sort_order", "name"))
    assert len(active) == 4
    assert {racer.slug for racer in active} == CANONICAL_SLUGS
    assert all(racer.tagline for racer in active)
    assert all(racer.backstory for racer in active)
    assert RoomSettings.load().runner_count == 4
    assert set(
        SpectatorSeatDefinition.objects.filter(active=True).values_list(
            "sprite_key",
            flat=True,
        )
    ) == {"rat", "slime", "bat", "mimic"}


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


def test_item_purchase_is_idempotent_and_inventory_is_capped_at_four() -> None:
    _current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Item Fan")
    speed = ItemDefinition.objects.get(slug="quantum-quencher")
    request_id = uuid.uuid4()

    original = purchase_item(
        player=player,
        item_slug=speed.slug,
        client_request_id=request_id,
    )
    duplicate = purchase_item(
        player=player,
        item_slug=speed.slug,
        client_request_id=request_id,
    )

    player.refresh_from_db()
    assert original.inventory_item_id == duplicate.inventory_item_id
    assert duplicate.duplicate is True
    assert player.balance_cents == RoomSettings.load().opening_balance_cents - speed.price_cents

    for slug in (
        "rubber-bone-broth",
        "potion-of-minor-inconvenience",
        "null-pointer-nectar",
    ):
        purchase_item(
            player=player,
            item_slug=slug,
            client_request_id=uuid.uuid4(),
        )

    with pytest.raises(ItemActionError) as caught:
        purchase_item(
            player=player,
            item_slug="maximum-ooze",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "inventory_full"
    assert InventoryItem.objects.filter(player=player, used_at__isnull=True).count() == 4


def test_discarding_an_item_frees_its_slot_without_a_refund() -> None:
    current_round, first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 20_000
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Bag Cleaner")
    purchases = [
        purchase_item(
            player=player,
            item_slug=slug,
            client_request_id=uuid.uuid4(),
        )
        for slug in (
            "quantum-quencher",
            "rubber-bone-broth",
            "banana-of-binding",
            "portable-pothole",
        )
    ]
    player.refresh_from_db()
    balance_after_purchases = player.balance_cents

    discarded = discard_inventory_item(
        player=player,
        inventory_item_id=purchases[0].inventory_item_id,
    )
    duplicate = discard_inventory_item(
        player=player,
        inventory_item_id=purchases[0].inventory_item_id,
    )

    assert discarded.duplicate is False
    assert duplicate.duplicate is True
    discarded_item = InventoryItem.objects.get(pk=purchases[0].inventory_item_id)
    assert discarded_item.discarded_at is not None
    player.refresh_from_db()
    assert player.balance_cents == balance_after_purchases
    assert len(build_live_state(player_id=player.pk)["player"]["inventory"]) == 3

    replacement = purchase_item(
        player=player,
        item_slug="maximum-ooze",
        client_request_id=uuid.uuid4(),
    )
    assert replacement.inventory_item_id != discarded_item.pk

    with pytest.raises(ItemActionError) as discarded_use:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=discarded_item.pk,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert discarded_use.value.code == "item_discarded"


def test_item_purchase_requires_money_and_live_item_rejects_outside_race() -> None:
    current_round, first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 5_000
    room.save()
    player = create_player(Device.objects.create(), "Broke Buyer")

    banana = ItemDefinition.objects.get(slug="banana-of-binding")
    pothole = ItemDefinition.objects.get(slug="portable-pothole")
    banana_purchase = purchase_item(
        player=player,
        item_slug=banana.slug,
        client_request_id=uuid.uuid4(),
    )
    with pytest.raises(ItemActionError) as funds_error:
        purchase_item(
            player=player,
            item_slug=pothole.slug,
            client_request_id=uuid.uuid4(),
        )
    assert funds_error.value.code == "insufficient_funds"

    player.refresh_from_db()
    assert player.balance_cents == 5_000 - banana.price_cents
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.ITEM).count() == 1

    current_round.state = Round.State.LOCKED
    current_round.save(update_fields=["state"])
    with pytest.raises(ItemActionError) as caught:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=banana_purchase.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert caught.value.code == "live_item_window_closed"
    assert InventoryItem.objects.get(pk=banana_purchase.inventory_item_id).used_at is None


def test_inventory_use_targets_portraits_and_enforces_round_limits() -> None:
    current_round, first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.max_round_item_uses = 10
    room.max_round_item_spend_cents = 8_000
    room.opening_balance_cents = 15_000
    room.save(
        update_fields=[
            "max_round_item_uses",
            "max_round_item_spend_cents",
            "opening_balance_cents",
            "updated_at",
        ]
    )
    player = create_player(Device.objects.create(), "Rules Reader")

    identity_purchases = [
        purchase_item(
            player=player,
            item_slug="identity-crisis-cordial",
            client_request_id=uuid.uuid4(),
        )
        for _index in range(2)
    ]
    for inventory_item in identity_purchases:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=inventory_item.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert RoundItemUse.objects.filter(
        player=player,
        round=current_round,
        item__slug="identity-crisis-cordial",
    ).count() == 2

    speed_purchase = purchase_item(
        player=player,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
    )
    speed_request_id = uuid.uuid4()
    speed_use = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=speed_purchase.inventory_item_id,
        client_request_id=speed_request_id,
        target_entry_id=first.pk,
    )
    duplicate_speed_use = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=speed_purchase.inventory_item_id,
        client_request_id=speed_request_id,
        target_entry_id=first.pk,
    )
    assert duplicate_speed_use.use_id == speed_use.use_id
    assert duplicate_speed_use.duplicate is True
    guard_purchase = purchase_item(
        player=player,
        item_slug="rubber-bone-broth",
        client_request_id=uuid.uuid4(),
    )
    with pytest.raises(ItemActionError) as spend_error:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=guard_purchase.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert spend_error.value.code == "item_spend_cap"
    assert InventoryItem.objects.get(pk=guard_purchase.inventory_item_id).used_at is None

    target_tester = create_player(Device.objects.create(), "Lane Inspector")
    pothole_purchase = purchase_item(
        player=target_tester,
        item_slug="portable-pothole",
        client_request_id=uuid.uuid4(),
    )
    current_round = start_live_round(current_round)
    with pytest.raises(ItemActionError) as target_error:
        use_inventory_item(
            player=target_tester,
            round_id=current_round.pk,
            inventory_item_id=pothole_purchase.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=999_999,
        )
    assert target_error.value.code == "unknown_racer"

    room.max_round_item_spend_cents = 10_000
    room.save(update_fields=["max_round_item_spend_cents", "updated_at"])
    track_use = use_inventory_item(
        player=target_tester,
        round_id=current_round.pk,
        inventory_item_id=pothole_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    stored_use = RoundItemUse.objects.get(pk=track_use.use_id)
    assert stored_use.target_entry == first
    assert stored_use.activation_tick > 0
    placement_tick = stored_use.activation_tick - round(0.25 * current_round.race.tick_rate)
    frame = max(
        (
            item
            for item in current_round.race.timeline
            if item["tick"] <= placement_tick
        ),
        key=lambda item: item["tick"],
    )
    target_frame = next(item for item in frame["racers"] if item["id"] == first.racer_id)
    assert stored_use.track_lane == pytest.approx(target_frame["y"])
    expected_position = min(max(target_frame["x"] + 0.08, 0.20), 0.925)
    assert stored_use.track_position == pytest.approx(expected_position)
    assert track_use.live_activation is True


def test_potions_are_assigned_before_start_and_track_items_are_used_live() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Phase Reader")
    speed_purchase = purchase_item(
        player=player,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
    )
    banana_purchase = purchase_item(
        player=player,
        item_slug="banana-of-binding",
        client_request_id=uuid.uuid4(),
    )

    potion_use = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=speed_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    assert potion_use.live_activation is False
    assert RoundItemUse.objects.get(pk=potion_use.use_id).activation_tick == 0

    with pytest.raises(ItemActionError) as early_item:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=banana_purchase.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert early_item.value.code == "live_item_window_closed"

    guard_purchase = purchase_item(
        player=player,
        item_slug="rubber-bone-broth",
        client_request_id=uuid.uuid4(),
    )
    current_round = start_live_round(current_round)
    with pytest.raises(ItemActionError) as late_potion:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=guard_purchase.inventory_item_id,
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert late_potion.value.code == "potion_window_closed"

    live_use = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=banana_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    assert live_use.live_activation is True
    assert RoundItemUse.objects.get(pk=live_use.use_id).activation_tick > 0


def test_live_item_regeneration_preserves_the_past_and_updates_the_future() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Timeline Inspector")
    oil_purchase = purchase_item(
        player=player,
        item_slug="open-source-oil-slick",
        client_request_id=uuid.uuid4(),
    )
    current_round = start_live_round(current_round, elapsed_seconds=3.0)
    original_timeline = current_round.race.timeline

    receipt = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=oil_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    stored_use = RoundItemUse.objects.get(pk=receipt.use_id)
    regenerate_live_race(current_round.pk)

    current_round.refresh_from_db()
    regenerated_timeline = current_round.race.timeline
    original_prefix = [
        frame for frame in original_timeline if frame["tick"] < stored_use.activation_tick
    ]
    regenerated_prefix = [
        frame
        for frame in regenerated_timeline
        if frame["tick"] < stored_use.activation_tick
    ]
    assert regenerated_prefix == original_prefix
    oil_effect = next(
        effect
        for effect in current_round.race.inputs["effects"]
        if effect["id"] == stored_use.pk
    )
    assert oil_effect["kind"] == ItemDefinition.Kind.OIL_SLICK
    assert oil_effect["activation_tick"] == stored_use.activation_tick
    assert all(
        event["tick"] >= stored_use.activation_tick
        for event in current_round.race.events
        if event["kind"] == "obstacle_hit"
        and event["message"].startswith(first.racer.name)
    )


def test_new_morph_tonics_are_seeded_as_racer_items() -> None:
    seed_catalog()

    morphs = ItemDefinition.objects.filter(
        kind__in=[
            ItemDefinition.Kind.GROWTH_TONIC,
            ItemDefinition.Kind.SHRINK_TONIC,
            ItemDefinition.Kind.TRANSFORM_TONIC,
        ]
    )

    assert morphs.count() == 3
    assert all(item.active for item in morphs)
    assert all(item.target == ItemDefinition.Target.RACER for item in morphs)
    max_item_spend = RoomSettings.load().max_round_item_spend_cents
    assert all(item.price_cents <= max_item_spend for item in morphs)


def test_live_item_catalog_has_five_distinct_track_effects() -> None:
    seed_catalog()

    live_items = ItemDefinition.objects.filter(
        kind__in=[
            ItemDefinition.Kind.BANANA,
            ItemDefinition.Kind.POTHOLE,
            ItemDefinition.Kind.OIL_SLICK,
            ItemDefinition.Kind.BOOST_PAD,
            ItemDefinition.Kind.BOXING_GLOVE,
        ]
    )

    assert live_items.count() == 5
    assert all(item.target == ItemDefinition.Target.TRACK for item in live_items)
    assert all(item.description.startswith("LIVE:") for item in live_items)


def test_catalog_prices_live_items_above_potions_and_seats_by_perk() -> None:
    seed_catalog()

    potions = ItemDefinition.objects.filter(kind__endswith="_tonic")
    live_items = ItemDefinition.objects.exclude(kind__endswith="_tonic")
    seats = list(SpectatorSeatDefinition.objects.order_by("sort_order"))

    assert min(potion.price_cents for potion in potions) >= 2_000
    assert max(potion.price_cents for potion in potions) < min(
        item.price_cents for item in live_items
    )
    assert [seat.price_cents for seat in seats] == [4_000, 6_000, 8_500, 15_000]
    assert [seat.payout_bonus_bps for seat in seats] == [500, 1_000, 1_500, 2_500]


def test_seat_claim_requires_available_money() -> None:
    current_round, _first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 400
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Standing Room")

    with pytest.raises(SeatClaimError) as caught:
        claim_seat(
            player=player,
            round_id=current_round.pk,
            seat_slug="finish-barrel",
            client_request_id=uuid.uuid4(),
        )

    assert caught.value.code == "insufficient_funds"
    player.refresh_from_db()
    assert player.balance_cents == 400


def test_seat_claim_is_exclusive_and_idempotent() -> None:
    current_round, _first, _second = open_round_with_entries()
    first_player = create_player(Device.objects.create(), "Seat One")
    second_player = create_player(Device.objects.create(), "Seat Two")
    request_id = uuid.uuid4()

    original = claim_seat(
        player=first_player,
        round_id=current_round.pk,
        seat_slug="finish-barrel",
        client_request_id=request_id,
    )
    duplicate = claim_seat(
        player=first_player,
        round_id=current_round.pk,
        seat_slug="finish-barrel",
        client_request_id=request_id,
    )
    assert original.claim_id == duplicate.claim_id
    assert duplicate.duplicate is True

    with pytest.raises(SeatClaimError, match="already") as caught:
        claim_seat(
            player=second_player,
            round_id=current_round.pk,
            seat_slug="finish-barrel",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "seat_taken"

    with pytest.raises(SeatClaimError, match="already claimed") as caught:
        claim_seat(
            player=first_player,
            round_id=current_round.pk,
            seat_slug="goblin-pit-rail",
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "seat_already_claimed"


def test_live_state_exposes_complete_party_game_contract() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Protocol Fan")
    speed_purchase = purchase_item(
        player=player,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
    )
    item_receipt = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=speed_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    purchase_item(
        player=player,
        item_slug="rubber-bone-broth",
        client_request_id=uuid.uuid4(),
    )
    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug="finish-barrel",
        client_request_id=uuid.uuid4(),
    )

    public_state = build_live_state(player_id=player.pk)

    assert public_state["protocol_version"] == 10
    assert public_state["room"]["max_inventory_items"] == 4
    assert public_state["room"]["max_round_item_spend_cents"] == 25_000
    assert len(public_state["room"]["item_catalog"]) == 12
    assert len(public_state["room"]["seat_catalog"]) == 4
    assert public_state["room"]["seat_catalog"][0]["sprite_key"] == "rat"
    assert public_state["room"]["seat_catalog"][0]["price_cents"] == 4_000
    assert public_state["room"]["seat_catalog"][0]["payout_bonus_bps"] == 500
    assert public_state["player"]["item_uses"][0]["kind"] == "speed_tonic"
    assert public_state["player"]["inventory"][0]["kind"] == "guard_tonic"
    assert public_state["round"]["item_uses"][0]["buyer"] == player.nickname
    assert public_state["round"]["item_uses"][0]["activation_tick"] == 0
    assert public_state["round"]["seats"][0]["nickname"] == player.nickname
    assert public_state["round"]["seats"][0]["player_id"] == player.pk
    assert public_state["round"]["seats"][0]["sprite_key"] == "rat"
    assert public_state["round"]["seats"][0]["payout_bonus_bps"] == 500
    assert "race" not in public_state["round"]

    advance_once(current_round.locks_at + timedelta(milliseconds=1))
    display_state = build_live_state(include_timeline=True)
    effect = display_state["round"]["race"]["effects"][0]
    assert effect["id"] == item_receipt.use_id
    assert effect["item_name"] == "Quantum Quencher"
    assert effect["target_racer_id"] == first.racer_id
    assert effect["activation_tick"] == 0
    outcome_ids = {
        *display_state["round"]["race"]["successful_effect_ids"],
        *display_state["round"]["race"]["failed_effect_ids"],
    }
    assert item_receipt.use_id in outcome_ids
