from __future__ import annotations

import pytest
from apps.players.middleware import encode_device_token
from apps.players.models import Device
from apps.players.services import create_player
from apps.racing.coordinator import advance_once
from apps.racing.models import Racer
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.conf import settings
from django.utils import timezone

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


def create_live_round() -> None:
    for index, slug in enumerate(("bonejamin", "spore-score", "gob-smack", "blinky")):
        Racer.objects.create(
            name=f"Socket Racer {index}",
            slug=slug,
            sprite_key=f"socket-racer-{index}",
            active=True,
            sort_order=index,
        )
    advance_once(timezone.now())


async def test_display_socket_receives_full_sync() -> None:
    await sync_to_async(create_live_round, thread_sensitive=True)()
    communicator = WebsocketCommunicator(application, "/ws/live/?role=display")

    connected, _subprotocol = await communicator.connect()
    message = await communicator.receive_json_from(timeout=2)

    assert connected is True
    assert message["type"] == "state.sync"
    assert message["state"]["protocol_version"] == 4
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
    await display.receive_json_from(timeout=2)

    await phone.send_json_to({"type": "audience.react", "kind": "cheer"})
    phone_message = await phone.receive_json_from(timeout=2)
    display_message = await display.receive_json_from(timeout=2)

    assert phone_message["type"] == "audience.reaction"
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
