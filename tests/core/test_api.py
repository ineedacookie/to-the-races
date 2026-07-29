from __future__ import annotations

import json
import uuid

import pytest
from apps.core import api
from apps.players.models import Device, Player
from apps.racing.item_services import ItemUseReceipt
from apps.racing.models import RoomSettings
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.test import Client

pytestmark = pytest.mark.django_db


def test_live_item_use_locks_the_room_before_mutating_or_regenerating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    original_select_for_update = RoomSettings.objects.select_for_update

    def lock_room() -> QuerySet[RoomSettings]:
        events.append("room")
        return original_select_for_update()

    def use_item(**_kwargs: object) -> ItemUseReceipt:
        assert transaction.get_connection().in_atomic_block
        events.append("item")
        return ItemUseReceipt(
            use_id=1,
            inventory_item_id=2,
            balance_cents=3,
            item_name="Banana",
            price_paid_cents=4,
            live_activation=True,
        )

    def regenerate(_round_id: int) -> None:
        assert transaction.get_connection().in_atomic_block
        events.append("regenerate")

    monkeypatch.setattr(RoomSettings.objects, "select_for_update", lock_room)
    monkeypatch.setattr(api, "use_inventory_item", use_item)
    monkeypatch.setattr(api, "regenerate_live_race", regenerate)

    api._use_item(
        Player(pk=1),
        {
            "round_id": 9,
            "inventory_item_id": 2,
            "target_entry_id": 3,
            "client_request_id": str(uuid.uuid4()),
        },
    )

    assert events == ["room", "item", "regenerate"]


def test_betting_page_sets_remembered_device_cookie() -> None:
    client = Client()

    response = client.get("/bet/")

    assert response.status_code == 200
    assert settings.DEVICE_COOKIE_NAME in response.cookies
    assert Device.objects.count() == 1


def test_betting_page_includes_tune_in_when_broadcast_is_enabled() -> None:
    room = RoomSettings.load()
    room.broadcast_enabled = True
    room.save(update_fields=["broadcast_enabled"])

    response = Client().get("/bet/")
    html = response.content.decode()

    assert 'id="bet-sheet-tab-tune-in"' in html
    assert 'id="tune-in-broadcast"' in html


def test_betting_page_omits_tune_in_when_broadcast_is_disabled() -> None:
    room = RoomSettings.load()
    room.broadcast_enabled = False
    room.save(update_fields=["broadcast_enabled"])

    response = Client().get("/bet/")
    html = response.content.decode()

    assert 'id="bet-sheet-tab-tune-in"' not in html
    assert 'id="bet-sheet-tune-in"' not in html
    assert 'id="tune-in-broadcast"' not in html


def test_live_state_exposes_system_broadcast_and_betting_settings() -> None:
    room = RoomSettings.load()
    room.broadcast_enabled = False
    room.betting_seconds = 47
    room.save(update_fields=["broadcast_enabled", "betting_seconds"])

    response = Client().get("/api/state/")

    assert response.status_code == 200
    assert response.json()["room"]["broadcast_enabled"] is False
    assert response.json()["room"]["betting_seconds"] == 47


def test_player_identity_is_remembered_by_the_same_client() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    created = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Lucky Goblin"}),
        content_type="application/json",
    )
    state = client.get("/api/state/")

    assert created.status_code == 200
    assert created.json()["player"]["nickname"] == "Lucky Goblin"
    assert state.json()["player"]["nickname"] == "Lucky Goblin"
    assert Player.objects.count() == 1


def test_duplicate_nickname_is_rejected_on_another_device() -> None:
    RoomSettings.load()
    first_client = Client()
    second_client = Client()
    first_client.get("/bet/")
    second_client.get("/bet/")
    first_client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Same Name"}),
        content_type="application/json",
    )

    response = second_client.post(
        "/api/player/",
        data=json.dumps({"nickname": "same name"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_nickname"


def test_blank_nickname_generates_a_fun_name() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    response = client.post(
        "/api/player/",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 200
    nickname = response.json()["player"]["nickname"]
    assert nickname.count("-") == 2


def test_existing_username_logs_in_on_another_device_without_logging_out_the_first() -> None:
    RoomSettings.load()
    first_client = Client()
    second_client = Client()
    first_client.get("/bet/")
    second_client.get("/bet/")
    created = first_client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Returning Goblin"}),
        content_type="application/json",
    ).json()["player"]
    player = Player.objects.get(pk=created["id"])
    player.balance_cents = 0
    player.save(update_fields=["balance_cents", "updated_at"])

    login = second_client.post(
        "/api/player/login/",
        data=json.dumps({"nickname": "returning goblin"}),
        content_type="application/json",
    )

    assert login.status_code == 200
    assert login.json()["player"]["id"] == player.pk
    assert login.json()["player"]["balance_cents"] == 0
    assert first_client.get("/api/state/").json()["player"]["id"] == player.pk
    assert second_client.get("/api/state/").json()["player"]["id"] == player.pk
    assert player.devices.count() == 2
    assert Player.objects.count() == 1


def test_login_rejects_an_unknown_username_without_creating_an_account() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    response = client.post(
        "/api/player/login/",
        data=json.dumps({"nickname": "Nobody Here"}),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "player_not_found"
    assert client.get("/api/state/").json()["player"] is None
    assert Player.objects.count() == 0
