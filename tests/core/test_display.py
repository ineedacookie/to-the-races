from __future__ import annotations

from django.test import Client
from django.urls import reverse


def test_display_can_only_be_embedded_by_the_same_origin() -> None:
    response = Client().get(reverse("display-page"))

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
