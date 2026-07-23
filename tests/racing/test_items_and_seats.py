from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from apps.betting.models import LedgerEntry
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import advance_once
from apps.racing.item_services import ItemDeployError, deploy_item
from apps.racing.management.commands.seed_game import CANONICAL_SLUGS
from apps.racing.models import (
    ItemDefinition,
    Race,
    RaceEntry,
    Racer,
    RoomSettings,
    Round,
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


def test_item_deploy_is_idempotent_and_respects_caps() -> None:
    current_round, first, _second = open_round_with_entries()
    player = create_player(Device.objects.create(), "Item Fan")
    speed = ItemDefinition.objects.get(slug="quantum-quencher")
    request_id = uuid.uuid4()

    original = deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug=speed.slug,
        client_request_id=request_id,
        target_entry_id=first.pk,
    )
    duplicate = deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug=speed.slug,
        client_request_id=request_id,
        target_entry_id=first.pk,
    )

    player.refresh_from_db()
    assert original.use_id == duplicate.use_id
    assert duplicate.duplicate is True
    assert player.balance_cents == RoomSettings.load().opening_balance_cents - speed.price_cents

    guard = ItemDefinition.objects.get(slug="rubber-bone-broth")
    trip = ItemDefinition.objects.get(slug="potion-of-minor-inconvenience")
    deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug=guard.slug,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug=trip.slug,
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )

    with pytest.raises(ItemDeployError) as caught:
        deploy_item(
            player=player,
            round_id=current_round.pk,
            item_slug="null-pointer-nectar",
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert caught.value.code == "item_use_cap"


def test_item_deploy_requires_available_money_and_rejects_after_lock() -> None:
    current_round, first, _second = open_round_with_entries()
    room = RoomSettings.load()
    room.opening_balance_cents = 500
    room.save()
    player = create_player(Device.objects.create(), "Broke Buyer")

    banana = ItemDefinition.objects.get(slug="banana-of-binding")
    pothole = ItemDefinition.objects.get(slug="portable-pothole")
    deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug=banana.slug,
        client_request_id=uuid.uuid4(),
        track_lane=1 / 3,
        track_position=0.5,
    )
    with pytest.raises(ItemDeployError) as funds_error:
        deploy_item(
            player=player,
            round_id=current_round.pk,
            item_slug=pothole.slug,
            client_request_id=uuid.uuid4(),
            track_lane=2 / 3,
            track_position=0.7,
        )
    assert funds_error.value.code == "insufficient_funds"

    player.refresh_from_db()
    assert player.balance_cents == 500 - banana.price_cents
    assert LedgerEntry.objects.filter(player=player, kind=LedgerEntry.Kind.ITEM).count() == 1

    current_round.state = Round.State.LOCKED
    current_round.save(update_fields=["state"])
    with pytest.raises(ItemDeployError) as caught:
        deploy_item(
            player=player,
            round_id=current_round.pk,
            item_slug="quantum-quencher",
            client_request_id=uuid.uuid4(),
            target_entry_id=first.pk,
        )
    assert caught.value.code == "betting_closed"


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
    item_receipt = deploy_item(
        player=player,
        round_id=current_round.pk,
        item_slug="quantum-quencher",
        client_request_id=uuid.uuid4(),
        target_entry_id=first.pk,
    )
    claim_seat(
        player=player,
        round_id=current_round.pk,
        seat_slug="finish-barrel",
        client_request_id=uuid.uuid4(),
    )

    public_state = build_live_state(player_id=player.pk)

    assert public_state["protocol_version"] == 2
    assert len(public_state["room"]["item_catalog"]) == 6
    assert len(public_state["room"]["seat_catalog"]) == 4
    assert public_state["room"]["seat_catalog"][0]["sprite_key"] == "rat"
    assert public_state["player"]["item_uses"][0]["kind"] == "speed_tonic"
    assert public_state["round"]["item_uses"][0]["buyer"] == player.nickname
    assert public_state["round"]["seats"][0]["nickname"] == player.nickname
    assert public_state["round"]["seats"][0]["sprite_key"] == "rat"
    assert "race" not in public_state["round"]

    advance_once(current_round.locks_at + timedelta(milliseconds=1))
    display_state = build_live_state(include_timeline=True)
    effect = display_state["round"]["race"]["effects"][0]
    assert effect["id"] == item_receipt.use_id
    assert effect["item_name"] == "Quantum Quencher"
    assert effect["target_racer_id"] == first.racer_id
