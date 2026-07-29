from __future__ import annotations

import json
from datetime import timedelta

import pytest
from apps.players.models import Player
from apps.racing.models import Race, RoomSettings, Round
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _identified_client(nickname: str = "Replay Fan") -> Client:
    RoomSettings.load()
    client = Client()
    client.get("/bet/")
    response = client.post(
        "/api/player/",
        data=json.dumps({"nickname": nickname}),
        content_type="application/json",
    )
    assert response.status_code == 200
    return client


def test_replay_preference_is_validated_and_follows_the_player_account() -> None:
    first_client = _identified_client()

    invalid = first_client.post(
        "/api/player/replay-preference/",
        data=json.dumps({"preference": "sometimes"}),
        content_type="application/json",
    )
    saved = first_client.post(
        "/api/player/replay-preference/",
        data=json.dumps({"preference": "always_watch"}),
        content_type="application/json",
    )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_replay_preference"
    assert saved.status_code == 200
    assert saved.json()["player"]["replay_preference"] == "always_watch"
    assert first_client.get("/api/state/").json()["player"]["replay_preference"] == "always_watch"

    second_client = Client()
    second_client.get("/bet/")
    login = second_client.post(
        "/api/player/login/",
        data=json.dumps({"nickname": "replay fan"}),
        content_type="application/json",
    )
    assert login.status_code == 200
    assert login.json()["player"]["replay_preference"] == "always_watch"
    assert Player.objects.get(nickname="Replay Fan").devices.count() == 2


def test_current_results_replay_requires_an_identified_player() -> None:
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=3),
        locks_at=now - timedelta(minutes=2),
        race_starts_at=now - timedelta(minutes=1),
        race_ends_at=now - timedelta(seconds=2),
        results_end_at=now + timedelta(seconds=20),
    )
    race = Race.objects.create(
        round=current_round,
        replay_montage={
            "version": 1,
            "playback_key": "1:2:key",
            "clips": [{"id": "clip-1"}],
        },
    )
    anonymous = Client()
    authenticated = _identified_client("Replay Viewer")
    next_round = Round.objects.create(
        number=2,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(seconds=20),
        race_starts_at=now + timedelta(seconds=23),
        race_ends_at=now + timedelta(minutes=1),
        results_end_at=now + timedelta(minutes=2),
    )
    Race.objects.create(round=next_round)

    unauthorized = anonymous.get(f"/api/rounds/{current_round.pk}/replay/")
    response = authenticated.get(f"/api/rounds/{current_round.pk}/replay/")

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["replay"]["playback_key"] == "1:2:key"

    race.replay_montage = {"version": 1, "playback_key": "empty", "clips": []}
    race.save(update_fields=["replay_montage"])
    assert authenticated.get(f"/api/rounds/{current_round.pk}/replay/").status_code == 409


def test_replay_endpoint_rejects_a_round_that_is_not_current_results() -> None:
    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.RACING,
        opened_at=now - timedelta(minutes=3),
        locks_at=now - timedelta(minutes=2),
        race_starts_at=now - timedelta(minutes=1),
        race_ends_at=now + timedelta(seconds=2),
        results_end_at=now + timedelta(seconds=20),
    )
    Race.objects.create(
        round=current_round,
        replay_montage={"version": 1, "playback_key": "not-ready", "clips": []},
    )
    client = _identified_client("Patient Viewer")

    response = client.get(f"/api/rounds/{current_round.pk}/replay/")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "replay_unavailable"
