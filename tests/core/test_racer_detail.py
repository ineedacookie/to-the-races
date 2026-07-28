from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.racing.models import Race, RaceEntry, Racer, Round
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


def make_racer(*, slug: str = "bonejamin", active: bool = True) -> Racer:
    return Racer.objects.create(
        name="Bonejamin",
        slug=slug,
        sprite_key="skeleton",
        color="#e8e0c9",
        tagline="Calcium-forward, latency-backward.",
        backstory="Assembled in a university robotics lab that pivoted to necromancy.",
        base_speed=0.94,
        resilience=0.72,
        recovery=0.48,
        aggression=0.62,
        chaos=0.55,
        active=active,
    )


def test_active_racer_has_a_public_dossier_page() -> None:
    racer = make_racer()

    response = Client().get(f"/racers/{racer.slug}/")

    assert response.status_code == 200
    assert b"Racer dossier" in response.content
    assert racer.name.encode() in response.content
    assert racer.backstory.encode() in response.content
    assert b"/static/assets/racers/portraits/skeleton.png" in response.content
    assert response.headers["Cache-Control"] == "no-store"


def test_racer_detail_shows_track_record_and_recent_history() -> None:
    racer = make_racer(slug="record-racer")
    now = timezone.now()
    older_round = Round.objects.create(
        number=4,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=10),
        locks_at=now - timedelta(minutes=9),
        race_starts_at=now - timedelta(minutes=8),
        race_ends_at=now - timedelta(minutes=7),
        results_end_at=now - timedelta(minutes=6),
        settled_at=now - timedelta(minutes=5),
    )
    older_race = Race.objects.create(
        round=older_round,
        completed_at=now - timedelta(minutes=5),
    )
    RaceEntry.objects.create(
        race=older_race,
        racer=racer,
        lane=1,
        odds=Decimal("5.00"),
        finish_place=None,
        dnf_reason="fire_pit",
    )
    current_round = Round.objects.create(
        number=5,
        state=Round.State.RESULTS,
        opened_at=now - timedelta(minutes=5),
        locks_at=now - timedelta(minutes=4),
        race_starts_at=now - timedelta(minutes=3),
        race_ends_at=now - timedelta(minutes=2),
        results_end_at=now - timedelta(minutes=1),
        settled_at=now,
    )
    race = Race.objects.create(round=current_round, completed_at=now)
    RaceEntry.objects.create(
        race=race,
        racer=racer,
        lane=2,
        odds=Decimal("4.25"),
        finish_place=1,
    )

    response = Client().get(f"/racers/{racer.slug}/")

    assert response.status_code == 200
    assert b"Track record" in response.content
    assert b"Rolling 50-race form" in response.content
    assert b"Fire pit" in response.content
    assert b"50.0%" in response.content
    assert "DNF · Fire pit".encode() in response.content
    assert b"Recent rounds" in response.content
    assert b"Round 5" in response.content
    assert b"Current odds" in response.content
    assert b"4.25" in response.content


def test_inactive_racer_dossier_is_not_public() -> None:
    racer = make_racer(slug="bench-racer", active=False)

    response = Client().get(f"/racers/{racer.slug}/")

    assert response.status_code == 404
