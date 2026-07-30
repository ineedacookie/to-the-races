from __future__ import annotations

from collections.abc import Iterator

import pytest
from apps.players.middleware import encode_device_token
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import advance_once, broadcast_current_state
from apps.racing.models import InventoryItem, ItemDefinition, Racer
from apps.realtime.presence import clear_presence
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.conf import settings
from django.utils import timezone

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def reset_presence_registry() -> Iterator[None]:
    clear_presence()
    yield
    clear_presence()


def create_live_round() -> None:
    for index, slug in enumerate(("bonejamin", "spore-score", "gob-smack", "blinky")):
        Racer.objects.create(
            name=f"Socket Racer {index}",
            slug=slug,
            sprite_key=f"socket-racer-{index}",
            active=True,
            sort_order=index,
        )
    ItemDefinition.objects.get_or_create(
        slug="test-speed-tonic",
        defaults={
            "name": "Test Speed Tonic",
            "description": "Test tonic",
            "icon": "⚡",
            "kind": ItemDefinition.Kind.SPEED_TONIC,
            "target": ItemDefinition.Target.RACER,
            "price_cents": 800,
            "effect_strength": 0.28,
        },
    )
    advance_once(timezone.now())


async def test_display_socket_receives_full_sync() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    communicator = WebsocketCommunicator(application, "/ws/live/?role=display")

    connected, _subprotocol = await communicator.connect()
    message = await communicator.receive_json_from(timeout=2)

    assert connected is True
    assert message["type"] == "state.sync"
    assert message["state"]["protocol_version"] == 18
    assert message["state"]["round"]["number"] == 1
    assert len(message["state"]["round"]["entries"]) == 4
    await communicator.disconnect()


async def test_authenticated_crowd_reaction_reaches_display_and_is_rate_limited() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    device = await sync_to_async(Device.objects.create, thread_sensitive=True)()
    player = await sync_to_async(create_player, thread_sensitive=True)(device, "Socket Heckler")
    cookie = encode_device_token(device.token)
    headers = [(b"cookie", f"{settings.DEVICE_COOKIE_NAME}={cookie}".encode())]
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)
    display = WebsocketCommunicator(application, "/ws/live/?role=display")
    await phone.connect()
    await display.connect()
    await phone.receive_json_from(timeout=2)
    own_presence = await phone.receive_json_from(timeout=2)
    assert own_presence["type"] == "presence.join"
    await display.receive_json_from(timeout=2)
    presence = await display.receive_json_from(timeout=2)
    assert presence["type"] == "presence.sync"
    assert presence["spectators"][0]["player_id"] == player.pk

    await phone.send_json_to({"type": "audience.react", "kind": "cheer"})
    phone_message = await phone.receive_json_from(timeout=2)
    display_message = await display.receive_json_from(timeout=2)

    assert phone_message["type"] == "audience.reaction"
    assert phone_message["reaction"]["player_id"] == player.pk
    assert phone_message["reaction"]["nickname"] == player.nickname
    assert phone_message["reaction"]["text"] == "CHEER!"
    assert phone_message["reaction"]["display_ms"] == 3_000
    assert display_message == phone_message

    await phone.send_json_to({"type": "audience.react", "kind": "boo"})
    rejected = await phone.receive_json_from(timeout=2)
    assert rejected["type"] == "audience.rejected"
    assert "three seconds" in rejected["message"]

    await phone.disconnect()
    await display.disconnect()


async def test_connected_bet_player_joins_and_leaves_display_bleachers() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    device = await sync_to_async(Device.objects.create, thread_sensitive=True)()
    player = await sync_to_async(create_player, thread_sensitive=True)(device, "Visible Viewer")
    cookie = encode_device_token(device.token)
    headers = [(b"cookie", f"{settings.DEVICE_COOKIE_NAME}={cookie}".encode())]
    display = WebsocketCommunicator(application, "/ws/live/?role=display")
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)

    await display.connect()
    await display.receive_json_from(timeout=2)
    initial_presence = await display.receive_json_from(timeout=2)
    assert initial_presence == {"type": "presence.sync", "spectators": []}

    await phone.connect()
    joined = await display.receive_json_from(timeout=2)
    await phone.receive_json_from(timeout=2)

    assert joined["type"] == "presence.join"
    assert joined["spectator"]["player_id"] == player.pk
    assert joined["spectator"]["nickname"] == player.nickname
    assert len(joined["spectator"]["avatar_version"]) == 16

    await phone.disconnect()
    left = await display.receive_json_from(timeout=2)
    assert left == {"type": "presence.leave", "player_id": player.pk}
    await display.disconnect()


async def test_betting_observer_receives_seat_owner_presence_changes() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    device = await sync_to_async(Device.objects.create, thread_sensitive=True)()
    player = await sync_to_async(create_player, thread_sensitive=True)(device, "Online Owner")
    cookie = encode_device_token(device.token)
    headers = [(b"cookie", f"{settings.DEVICE_COOKIE_NAME}={cookie}".encode())]
    observer = WebsocketCommunicator(application, "/ws/live/?role=bet")
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)

    await observer.connect()
    await observer.receive_json_from(timeout=2)
    await phone.connect()
    await phone.receive_json_from(timeout=2)

    joined = await observer.receive_json_from(timeout=2)
    assert joined["type"] == "presence.join"
    assert joined["spectator"]["player_id"] == player.pk

    await phone.disconnect()
    left = await observer.receive_json_from(timeout=2)
    assert left == {"type": "presence.leave", "player_id": player.pk}
    await observer.disconnect()


async def test_multiple_tabs_and_devices_share_one_bleacher_person() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    device = await sync_to_async(Device.objects.create, thread_sensitive=True)()
    player = await sync_to_async(create_player, thread_sensitive=True)(device, "One Person")
    second_device = await sync_to_async(Device.objects.create, thread_sensitive=True)(player=player)
    cookie = encode_device_token(device.token)
    headers = [(b"cookie", f"{settings.DEVICE_COOKIE_NAME}={cookie}".encode())]
    second_device_cookie = encode_device_token(second_device.token)
    second_device_headers = [
        (b"cookie", f"{settings.DEVICE_COOKIE_NAME}={second_device_cookie}".encode())
    ]
    display = WebsocketCommunicator(application, "/ws/live/?role=display")
    first_phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)
    second_phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)
    other_device_phone = WebsocketCommunicator(
        application,
        "/ws/live/?role=bet",
        headers=second_device_headers,
    )

    await display.connect()
    await display.receive_json_from(timeout=2)
    await display.receive_json_from(timeout=2)
    await first_phone.connect()
    await first_phone.receive_json_from(timeout=2)
    joined = await display.receive_json_from(timeout=2)
    assert joined["type"] == "presence.join"

    await second_phone.connect()
    await second_phone.receive_json_from(timeout=2)
    assert await display.receive_nothing(timeout=0.1)

    await other_device_phone.connect()
    await other_device_phone.receive_json_from(timeout=2)
    assert await display.receive_nothing(timeout=0.1)

    await first_phone.disconnect()
    assert await display.receive_nothing(timeout=0.1)
    await second_phone.disconnect()
    assert await display.receive_nothing(timeout=0.1)
    await other_device_phone.disconnect()
    left = await display.receive_json_from(timeout=2)
    assert left == {"type": "presence.leave", "player_id": player.pk}
    await display.disconnect()


async def test_bet_socket_receives_broadcast_state_events() -> None:
    """Verify that broadcast_current_state delivers events to connected bet clients."""
    await sync_to_async(create_live_round, thread_sensitive=True)()
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet")
    await phone.connect()
    await phone.receive_json_from(timeout=2)  # state.sync
    await phone.receive_nothing(timeout=0.1)  # no presence

    await broadcast_current_state("race.started")

    message = await phone.receive_json_from(timeout=2)
    assert message["type"] == "race.started"
    assert "state" in message
    assert "round" in message["state"]
    assert "show_round" in message["state"]
    assert "room" in message["state"]
    assert "item_catalog" in message["state"]["room"]
    await phone.disconnect()


async def test_bet_socket_receives_fresh_personal_state_with_broadcast() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    device = await sync_to_async(Device.objects.create, thread_sensitive=True)()
    player = await sync_to_async(create_player, thread_sensitive=True)(device, "Bag Owner")
    cookie = encode_device_token(device.token)
    headers = [(b"cookie", f"{settings.DEVICE_COOKIE_NAME}={cookie}".encode())]
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet", headers=headers)
    await phone.connect()
    initial = await phone.receive_json_from(timeout=2)
    assert initial["state"]["player"]["inventory"] == []
    presence = await phone.receive_json_from(timeout=2)
    assert presence["type"] == "presence.join"

    item = await sync_to_async(
        ItemDefinition.objects.get,
        thread_sensitive=True,
    )(slug="test-speed-tonic")
    await sync_to_async(InventoryItem.objects.create, thread_sensitive=True)(
        player=player,
        item=item,
        price_paid_cents=item.price_cents,
    )
    await broadcast_current_state("items.updated")

    message = await phone.receive_json_from(timeout=2)
    assert message["type"] == "items.updated"
    assert [entry["item_name"] for entry in message["state"]["player"]["inventory"]] == [
        item.name
    ]
    await phone.disconnect()


async def test_display_socket_receives_broadcast_state_events() -> None:
    """Verify that broadcast_current_state delivers events to display clients."""
    await sync_to_async(create_live_round, thread_sensitive=True)()
    display = WebsocketCommunicator(application, "/ws/live/?role=display")
    await display.connect()
    await display.receive_json_from(timeout=2)  # state.sync
    await display.receive_json_from(timeout=2)  # presence.sync

    await broadcast_current_state("round.opened")

    message = await display.receive_json_from(timeout=2)
    assert message["type"] == "round.opened"
    assert "state" in message
    assert "item_catalog" in message["state"]["room"]
    await display.disconnect()


async def test_broadcast_item_catalog_includes_discounts() -> None:
    """Verify that broadcast state item_catalog has discount_pct and effective_price_cents."""
    await sync_to_async(create_live_round, thread_sensitive=True)()
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet")
    await phone.connect()
    await phone.receive_json_from(timeout=2)  # state.sync
    await phone.receive_nothing(timeout=0.1)

    await broadcast_current_state("round.opened")

    message = await phone.receive_json_from(timeout=2)
    catalog = message["state"]["room"]["item_catalog"]
    assert len(catalog) > 0
    for item in catalog:
        assert "discount_pct" in item
        assert "effective_price_cents" in item
        assert "price_cents" in item
        if item["discount_pct"] > 0:
            expected = item["price_cents"] * (100 - item["discount_pct"]) // 100
            assert item["effective_price_cents"] == expected
    await phone.disconnect()


async def test_race_started_and_round_opened_reach_client_sequentially() -> None:
    """Verify both race.started and round.opened arrive at the client."""
    await sync_to_async(create_live_round, thread_sensitive=True)()
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet")
    await phone.connect()
    await phone.receive_json_from(timeout=2)  # state.sync
    await phone.receive_nothing(timeout=0.1)

    await broadcast_current_state("race.started")
    msg1 = await phone.receive_json_from(timeout=2)
    assert msg1["type"] == "race.started"

    await broadcast_current_state("round.opened")
    msg2 = await phone.receive_json_from(timeout=2)
    assert msg2["type"] == "round.opened"
    assert msg2["state"]["room"]["item_catalog"]

    await phone.disconnect()


async def test_bet_socket_receives_sync_request() -> None:
    """Verify that the client can request a fresh state.sync."""
    await sync_to_async(create_live_round, thread_sensitive=True)()
    phone = WebsocketCommunicator(application, "/ws/live/?role=bet")
    await phone.connect()
    first_sync = await phone.receive_json_from(timeout=2)
    assert first_sync["type"] == "state.sync"

    await phone.send_json_to({"type": "sync.request"})
    second_sync = await phone.receive_json_from(timeout=2)
    assert second_sync["type"] == "state.sync"
    assert second_sync["state"]["round"]["state"] == "open"
    await phone.disconnect()
