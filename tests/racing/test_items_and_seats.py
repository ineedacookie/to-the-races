from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from apps.betting.models import LedgerEntry
from apps.betting.services import place_bet, settle_round
from apps.players.models import Device, Player
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
    RoundDiscount,
    RoundItemUse,
    RoundSeatMarket,
    SeatOwnership,
    SpectatorSeatDefinition,
)
from apps.racing.seat_services import (
    TAKEOVER_PRICE_INCREMENT_CENTS,
    SeatClaimError,
    claim_seat,
    ensure_round_seat_markets,
)
from apps.racing.serializers import build_live_state
from django.core.management import call_command
from django.db import close_old_connections
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
        create_seat_markets=True,
    )


def start_live_round(current_round: Round, *, elapsed_seconds: float = 2.0) -> Round:
    now = timezone.now()
    current_round.locks_at = now - timedelta(seconds=elapsed_seconds + 1)
    current_round.race_starts_at = now - timedelta(seconds=elapsed_seconds)
    current_round.save(update_fields=["locks_at", "race_starts_at"])
    with patch("apps.racing.coordinator.secrets.randbits", return_value=0):
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
    room.opening_balance_cents = 3_000
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
    assert player.balance_cents == 3_000 - banana.price_cents
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
    room.max_round_item_spend_cents = 10_400
    room.opening_balance_cents = 20_000
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
    assert (
        RoundItemUse.objects.filter(
            player=player,
            round=current_round,
            item__slug="identity-crisis-cordial",
        ).count()
        == 2
    )

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
        (item for item in current_round.race.timeline if item["tick"] <= placement_tick),
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


def test_paused_room_blocks_potions_and_seat_claims() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Paused Shopper")
    purchase = purchase_item(
        player=player,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
    )
    room = RoomSettings.load()
    room.is_paused = True
    room.save(update_fields=["is_paused"])

    with pytest.raises(ItemActionError) as potion_error:
        use_inventory_item(
            player=player,
            round_id=current_round.pk,
            inventory_item_id=purchase.inventory_item_id,
            target_entry_id=first.pk,
            client_request_id=uuid.uuid4(),
        )
    seat = SpectatorSeatDefinition.objects.filter(active=True).first()
    assert seat is not None
    market = RoundSeatMarket.objects.get(round=current_round, seat=seat)
    with pytest.raises(SeatClaimError) as seat_error:
        claim_seat(
            player=player,
            round_id=current_round.pk,
            seat_slug=seat.slug,
            expected_price_cents=market.current_price_cents,
            client_request_id=uuid.uuid4(),
        )

    assert potion_error.value.code == "potion_window_closed"
    assert seat_error.value.code == "betting_closed"


@pytest.mark.parametrize(
    "slug",
    [
        "nitro-serum",
        "recovery-brew",
        "ghost-draught",
        "second-wind",
        "phoenix-flask",
    ],
)
def test_new_potions_without_tonic_suffix_still_use_the_prerace_window(slug: str) -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), f"Potion {slug[:8]}")
    purchase = purchase_item(
        player=player,
        item_slug=slug,
        client_request_id=uuid.uuid4(),
    )

    receipt = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )

    assert receipt.live_activation is False
    assert RoundItemUse.objects.get(pk=receipt.use_id).activation_tick == 0


def test_live_item_regeneration_preserves_the_past_and_updates_the_future() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Timeline Inspector")
    oil_purchase = purchase_item(
        player=player,
        item_slug="open-source-oil-slick",
        client_request_id=uuid.uuid4(),
    )
    current_round = start_live_round(current_round, elapsed_seconds=3.0)
    original_timeline = current_round.race.timeline
    current_tick = 3 * current_round.race.tick_rate
    current_frame = max(
        (frame for frame in original_timeline if frame["tick"] <= current_tick),
        key=lambda frame: frame["tick"],
    )
    active_racer_id = next(
        racer["id"]
        for racer in current_frame["racers"]
        if racer["state"] in {"running", "backwards", "fallen"}
    )
    target_entry = RaceEntry.objects.select_related("racer").get(
        race=current_round.race,
        racer_id=active_racer_id,
    )

    receipt = use_inventory_item(
        player=player,
        round_id=current_round.pk,
        inventory_item_id=oil_purchase.inventory_item_id,
        client_request_id=uuid.uuid4(),
        target_entry_id=target_entry.pk,
    )
    stored_use = RoundItemUse.objects.get(pk=receipt.use_id)
    regenerate_live_race(current_round.pk)

    current_round.refresh_from_db()
    regenerated_timeline = current_round.race.timeline
    original_prefix = [
        frame for frame in original_timeline if frame["tick"] < stored_use.activation_tick
    ]
    regenerated_prefix = [
        frame for frame in regenerated_timeline if frame["tick"] < stored_use.activation_tick
    ]
    assert regenerated_prefix == original_prefix
    oil_effect = next(
        effect for effect in current_round.race.inputs["effects"] if effect["id"] == stored_use.pk
    )
    assert oil_effect["kind"] == ItemDefinition.Kind.OIL_SLICK
    assert oil_effect["activation_tick"] == stored_use.activation_tick
    assert all(
        event["tick"] >= stored_use.activation_tick
        for event in current_round.race.events
        if event["kind"] == "obstacle_hit" and event["message"].startswith(target_entry.racer.name)
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


def test_live_item_catalog_has_fourteen_distinct_track_effects() -> None:
    seed_catalog()

    live_items = ItemDefinition.objects.filter(target=ItemDefinition.Target.TRACK)

    assert live_items.count() == 14
    assert live_items.values("kind").distinct().count() == 14
    assert all(item.target == ItemDefinition.Target.TRACK for item in live_items)
    assert all(not item.description.startswith("LIVE") for item in live_items)
    assert all("proc" not in item.description.lower() for item in live_items)


def test_catalog_prices_support_common_items_and_rare_power_plays() -> None:
    seed_catalog()

    items = {item.slug: item.price_cents for item in ItemDefinition.objects.all()}
    seats = list(SpectatorSeatDefinition.objects.order_by("sort_order"))

    assert items == {
        "quantum-quencher": 800,
        "rubber-bone-broth": 800,
        "potion-of-minor-inconvenience": 640,
        "null-pointer-nectar": 800,
        "maximum-ooze": 800,
        "fun-size-fizz": 640,
        "identity-crisis-cordial": 4_800,
        "fireproof-tonic": 2_000,
        "nitro-serum": 800,
        "recovery-brew": 640,
        "ghost-draught": 1_600,
        "second-wind": 800,
        "phoenix-flask": 4_800,
        "invincibility-tonic": 8_000,
        "berserk-potion": 6_400,
        "banana-of-binding": 1_200,
        "portable-pothole": 2_000,
        "open-source-oil-slick": 1_600,
        "questionable-boost-pad": 2_400,
        "spring-loaded-boxing-glove": 6_400,
        "detour-sign": 1_600,
        "speed-bump": 1_200,
        "stop-sign": 1_600,
        "glass-door": 2_000,
        "rock-wall": 2_400,
        "roomba-vacuum": 1_600,
        "springboard": 2_000,
        "magnet-mine": 2_400,
        "portal-gate": 4_800,
    }
    assert [seat.price_cents for seat in seats] == [4_000, 6_000, 8_500, 15_000]
    assert [seat.payout_bonus_bps for seat in seats] == [500, 1_000, 1_500, 2_500]


def test_seat_takeover_requires_available_money() -> None:
    current_round, _first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 400
    room.save(update_fields=["opening_balance_cents", "updated_at"])
    player = create_player(Device.objects.create(), "Standing Room")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")

    with pytest.raises(SeatClaimError) as caught:
        claim_seat(
            player=player,
            round_id=current_round.pk,
            seat_slug=seat.slug,
            expected_price_cents=seat.price_cents,
            client_request_id=uuid.uuid4(),
        )

    assert caught.value.code == "insufficient_funds"
    player.refresh_from_db()
    assert player.balance_cents == 400


def test_seat_takeover_is_idempotent_and_raises_price_by_five_dollars() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Seat One")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")
    request_id = uuid.uuid4()

    original = claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=request_id,
    )
    duplicate = claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=request_id,
    )
    market = RoundSeatMarket.objects.get(round=current_round, seat=seat)

    assert original.claim_id == duplicate.claim_id
    assert duplicate.duplicate is True
    assert original.price_paid_cents == seat.price_cents
    assert original.next_price_cents == seat.price_cents + TAKEOVER_PRICE_INCREMENT_CENTS
    assert market.current_price_cents == seat.price_cents + TAKEOVER_PRICE_INCREMENT_CENTS
    assert market.takeover_count == 1
    assert SeatOwnership.objects.filter(player=player, seat=seat).exists()


def test_seat_takeover_refunds_half_of_the_displaced_owner_purchase() -> None:
    current_round, _first, _second = open_round_with_entries()
    owner = create_player(Device.objects.create(), "Seat Owner")
    challenger = create_player(Device.objects.create(), "Seat Raider")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")
    starting_balance = owner.balance_cents

    claim_seat(
        player=owner,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=uuid.uuid4(),
    )
    market = RoundSeatMarket.objects.get(round=current_round, seat=seat)

    takeover = claim_seat(
        player=challenger,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=market.current_price_cents,
        client_request_id=uuid.uuid4(),
    )

    owner.refresh_from_db()
    challenger.refresh_from_db()
    market.refresh_from_db()

    assert owner.balance_cents == starting_balance - seat.price_cents // 2
    assert takeover.price_paid_cents == seat.price_cents + TAKEOVER_PRICE_INCREMENT_CENTS
    assert SeatOwnership.objects.get(seat=seat).player_id == challenger.pk
    assert not SeatOwnership.objects.filter(player=owner).exists()
    assert owner.ledger_entries.filter(
        kind=LedgerEntry.Kind.REFUND,
        amount_cents=seat.price_cents // 2,
        description__contains=seat.name,
    ).exists()

    with pytest.raises(SeatClaimError) as self_purchase:
        claim_seat(
            player=challenger,
            round_id=current_round.pk,
            seat_slug=seat.slug,
            expected_price_cents=market.current_price_cents,
            client_request_id=uuid.uuid4(),
        )
    assert self_purchase.value.code == "self_purchase"


def test_seat_switching_vacates_old_seat_atomically() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Seat Hopper")
    cheap = SpectatorSeatDefinition.objects.get(slug="finish-barrel")
    premium = SpectatorSeatDefinition.objects.get(slug="goblin-pit-rail")

    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=cheap.slug,
        expected_price_cents=cheap.price_cents,
        client_request_id=uuid.uuid4(),
    )
    premium_market = RoundSeatMarket.objects.get(round=current_round, seat=premium)
    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=premium.slug,
        expected_price_cents=premium_market.current_price_cents,
        client_request_id=uuid.uuid4(),
    )

    assert SeatOwnership.objects.filter(player=player).count() == 1
    assert SeatOwnership.objects.get(player=player).seat_id == premium.pk
    assert not SeatOwnership.objects.filter(seat=cheap).exists()


def test_stale_expected_price_is_rejected() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Stale Click")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")

    with pytest.raises(SeatClaimError) as caught:
        claim_seat(
            player=player,
            round_id=current_round.pk,
            seat_slug=seat.slug,
            expected_price_cents=seat.price_cents + 999,
            client_request_id=uuid.uuid4(),
        )
    assert caught.value.code == "stale_price"


def test_seat_market_setup_tolerates_a_concurrent_creator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_round, _first, _second = create_open_round_with_entries(
        use_catalog=True,
        create_seat_markets=False,
    )
    original_bulk_create = RoundSeatMarket.objects.bulk_create

    def create_one_then_bulk(
        markets: list[RoundSeatMarket],
        *,
        ignore_conflicts: bool = False,
    ) -> list[RoundSeatMarket]:
        first = markets[0]
        RoundSeatMarket.objects.create(
            round_id=first.round_id,
            seat_id=first.seat_id,
            current_price_cents=first.current_price_cents,
            takeover_count=first.takeover_count,
        )
        return original_bulk_create(markets, ignore_conflicts=ignore_conflicts)

    monkeypatch.setattr(RoundSeatMarket.objects, "bulk_create", create_one_then_bulk)

    ensure_round_seat_markets(current_round)

    assert RoundSeatMarket.objects.filter(round=current_round).count() == (
        SpectatorSeatDefinition.objects.filter(active=True).count()
    )


def test_seat_ownership_persists_and_market_resets_on_new_round() -> None:
    current_round, _first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Persistent Owner")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")

    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=uuid.uuid4(),
    )
    escalated_market = RoundSeatMarket.objects.get(round=current_round, seat=seat)
    assert escalated_market.takeover_count == 1

    now = timezone.now()
    next_round = Round.objects.create(
        number=2,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(minutes=1),
        race_starts_at=now + timedelta(minutes=2),
        race_ends_at=now + timedelta(minutes=3),
        results_end_at=now + timedelta(minutes=4),
    )
    Race.objects.create(round=next_round)
    ensure_round_seat_markets(next_round)

    reset_market = RoundSeatMarket.objects.get(round=next_round, seat=seat)
    assert reset_market.current_price_cents == seat.price_cents
    assert reset_market.takeover_count == 0
    assert SeatOwnership.objects.get(seat=seat).player_id == player.pk


def test_seat_payout_bonus_applies_while_owner_retains_seat() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Bonus Holder")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")
    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=uuid.uuid4(),
    )
    place_bet(
        player=player,
        race_entry_id=first.pk,
        amount_cents=500,
        client_request_id=uuid.uuid4(),
    )
    first.finish_place = 1
    first.finish_tick = 100
    first.save(update_fields=["finish_place", "finish_tick"])
    current_round.race.completed_at = timezone.now()
    current_round.race.save(update_fields=["completed_at"])

    settle_round(current_round.pk)

    player.refresh_from_db()
    bet = player.bets.get()
    assert bet.payout_cents == 1_550
    assert player.ledger_entries.filter(description__contains=seat.name).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_seat_takeovers_allow_one_winner_and_stale_loser() -> None:
    current_round, _first, _second = open_round_with_entries()
    owner = create_player(Device.objects.create(), "Incumbent")
    challenger_a = create_player(Device.objects.create(), "Challenger A")
    challenger_b = create_player(Device.objects.create(), "Challenger B")
    seat = SpectatorSeatDefinition.objects.get(slug="finish-barrel")
    barrier = Barrier(2)

    claim_seat(
        player=owner,
        round_id=current_round.pk,
        seat_slug=seat.slug,
        expected_price_cents=seat.price_cents,
        client_request_id=uuid.uuid4(),
    )
    market = RoundSeatMarket.objects.get(round=current_round, seat=seat)
    expected_price = market.current_price_cents
    outcomes: list[str] = []

    def submit(player_id: int) -> None:
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            claim_seat(
                player=Player.objects.get(pk=player_id),
                round_id=current_round.pk,
                seat_slug=seat.slug,
                expected_price_cents=expected_price,
                client_request_id=uuid.uuid4(),
            )
            outcomes.append("ok")
        except SeatClaimError as error:
            outcomes.append(error.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.map(
            lambda player_id: submit(player_id),
            [challenger_a.pk, challenger_b.pk],
        )

    market.refresh_from_db()
    assert outcomes.count("ok") == 1
    assert outcomes.count("stale_price") == 1
    assert market.takeover_count == 2
    assert market.current_price_cents == seat.price_cents + 2 * TAKEOVER_PRICE_INCREMENT_CENTS
    assert SeatOwnership.objects.get(seat=seat).player_id in {challenger_a.pk, challenger_b.pk}


def test_live_state_exposes_seat_markets_and_persistent_ownership() -> None:
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
        expected_price_cents=4_000,
        client_request_id=uuid.uuid4(),
    )

    public_state = build_live_state(player_id=player.pk)

    assert public_state["protocol_version"] == 18
    assert public_state["room"]["max_inventory_items"] == 4
    assert len(public_state["room"]["upgrade_catalog"]) == 2
    assert public_state["room"]["max_round_stake_cents"] == 15_000
    assert public_state["room"]["max_round_item_spend_cents"] == 25_000
    assert len(public_state["room"]["item_catalog"]) == 29
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
    assert public_state["round"]["seats"][0]["current_price_cents"] == 4_500
    assert public_state["round"]["seats"][0]["takeover_count"] == 1
    finish_barrel_market = next(
        market
        for market in public_state["round"]["seat_markets"]
        if market["seat_slug"] == "finish-barrel"
    )
    assert finish_barrel_market["current_price_cents"] == 4_500
    assert finish_barrel_market["takeover_count"] == 1
    assert public_state["player"]["seat_claim"]["seat_slug"] == "finish-barrel"
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


def test_purchase_applies_round_discount() -> None:
    current_round, _first, _second = open_round_with_entries()
    seed_catalog()
    player = create_player(Device.objects.create(), "Discount Hunter")
    speed = ItemDefinition.objects.get(slug="quantum-quencher")
    original_price = speed.price_cents

    RoundDiscount.objects.create(
        round=current_round,
        item=speed,
        discount_pct=40,
    )
    expected_discounted = original_price * 60 // 100

    receipt = purchase_item(
        player=player,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
    )

    assert receipt.price_paid_cents == expected_discounted
    inv = InventoryItem.objects.get(pk=receipt.inventory_item_id)
    assert inv.price_paid_cents == expected_discounted
    player.refresh_from_db()
    room = RoomSettings.load()
    assert player.balance_cents == room.opening_balance_cents - expected_discounted


def test_discounted_price_appears_in_live_state_catalog() -> None:
    current_round, _first, _second = open_round_with_entries()
    seed_catalog()
    speed = ItemDefinition.objects.get(slug="quantum-quencher")
    RoundDiscount.objects.create(
        round=current_round,
        item=speed,
        discount_pct=25,
    )
    state = build_live_state()
    catalog_item = next(
        item for item in state["room"]["item_catalog"] if item["slug"] == "quantum-quencher"
    )
    assert catalog_item["discount_pct"] == 25
    assert catalog_item["effective_price_cents"] == speed.price_cents * 75 // 100
