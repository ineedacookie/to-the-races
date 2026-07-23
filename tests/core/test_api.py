from __future__ import annotations

import json

import pytest
from apps.players.models import Device, Player
from apps.racing.models import RoomSettings
from django.conf import settings
from django.test import Client

pytestmark = pytest.mark.django_db


def test_betting_page_sets_remembered_device_cookie() -> None:
    client = Client()

    response = client.get("/bet/")

    assert response.status_code == 200
    assert settings.DEVICE_COOKIE_NAME in response.cookies
    assert Device.objects.count() == 1


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
