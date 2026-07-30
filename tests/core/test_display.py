from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse


def test_display_can_only_be_embedded_by_the_same_origin() -> None:
    response = Client().get(reverse("display-page"))

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


@pytest.mark.django_db
def test_pages_omit_unused_cross_origin_opener_policy() -> None:
    response = Client().get(reverse("betting-page"))

    assert response.status_code == 200
    assert "Cross-Origin-Opener-Policy" not in response.headers
    assert b'allow="fullscreen"' in response.content
    assert b"allowfullscreen" not in response.content
