from __future__ import annotations

import pytest
from apps.racing.models import Racer
from django.test import Client

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


def test_inactive_racer_dossier_is_not_public() -> None:
    racer = make_racer(slug="bench-racer", active=False)

    response = Client().get(f"/racers/{racer.slug}/")

    assert response.status_code == 404
