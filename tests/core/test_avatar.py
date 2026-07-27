from __future__ import annotations

import json
from io import BytesIO

import pytest
from apps.players.models import Player
from apps.racing.models import RoomSettings
from django.test import Client
from PIL import Image

pytestmark = pytest.mark.django_db

CUSTOM_RECIPE = {
    "skin": 4,
    "eyes": 8,
    "bottoms": 37,
    "tops": 102,
    "shoes": 21,
    "hair": 44,
}


def test_identity_saves_and_serves_a_custom_pixel_person() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    identity_response = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Wardrobe Wizard", "avatar": CUSTOM_RECIPE}),
        content_type="application/json",
    )

    assert identity_response.status_code == 200
    payload = identity_response.json()["player"]
    player = Player.objects.get(pk=payload["id"])
    assert player.avatar_recipe == CUSTOM_RECIPE
    assert payload["avatar_url"].endswith(f"?v={payload['avatar_version']}")

    avatar_response = client.get(payload["avatar_url"])
    assert avatar_response.status_code == 200
    assert avatar_response.headers["Content-Type"] == "image/png"
    assert "immutable" in avatar_response.headers["Cache-Control"]
    assert avatar_response.headers["ETag"] == f'"{payload["avatar_version"]}"'
    with Image.open(BytesIO(avatar_response.content)) as avatar:
        assert avatar.size == (64, 112)
        assert avatar.mode == "RGBA"
        assert avatar.getbbox() is not None

    cached_response = client.get(
        payload["avatar_url"],
        headers={"If-None-Match": avatar_response.headers["ETag"]},
    )
    assert cached_response.status_code == 304


def test_identity_rejects_incomplete_or_out_of_range_avatar_recipes() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    incomplete = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Missing Layers", "avatar": {"skin": 1}}),
        content_type="application/json",
    )
    out_of_range = client.post(
        "/api/player/",
        data=json.dumps(
            {
                "nickname": "Wild Hair",
                "avatar": {**CUSTOM_RECIPE, "hair": 65},
            }
        ),
        content_type="application/json",
    )

    assert incomplete.status_code == 400
    assert incomplete.json()["error"]["code"] == "invalid_avatar"
    assert out_of_range.status_code == 400
    assert out_of_range.json()["error"]["code"] == "invalid_avatar"
    assert Player.objects.count() == 0


def test_identity_without_avatar_gets_a_stable_default_recipe() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")

    response = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Default Dresser"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    player = Player.objects.get()
    assert set(player.avatar_recipe) == set(CUSTOM_RECIPE)
    assert all(isinstance(index, int) for index in player.avatar_recipe.values())


def test_existing_player_can_update_their_name_and_avatar() -> None:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")
    created = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "First Look", "avatar": CUSTOM_RECIPE}),
        content_type="application/json",
    ).json()["player"]
    updated_recipe = {**CUSTOM_RECIPE, "hair": 45}

    updated_response = client.post(
        "/api/player/",
        data=json.dumps({"nickname": "Second Look", "avatar": updated_recipe}),
        content_type="application/json",
    )

    assert updated_response.status_code == 200
    updated = updated_response.json()["player"]
    assert updated["id"] == created["id"]
    assert updated["nickname"] == "Second Look"
    assert updated["avatar_version"] != created["avatar_version"]
    assert Player.objects.get().avatar_recipe == updated_recipe
    assert Player.objects.count() == 1
