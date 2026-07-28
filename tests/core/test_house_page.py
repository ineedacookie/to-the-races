from __future__ import annotations

import pytest
from apps.betting.models import LedgerEntry
from apps.players.models import Device
from apps.players.services import create_player
from django.test import Client

pytestmark = pytest.mark.django_db


def test_house_account_is_public_and_shows_derived_activity() -> None:
    player = create_player(Device.objects.create(), "Public Counterparty")
    LedgerEntry.objects.create(
        player=player,
        kind=LedgerEntry.Kind.ITEM,
        amount_cents=-2_500,
        balance_after_cents=player.balance_cents,
        description="Bought trouble",
    )

    response = Client().get("/house/")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert b"The House Account" in response.content
    assert b"Lifetime breakdown" in response.content
    assert b"Items sold" in response.content
    assert b"$25" in response.content
    assert b"Public Counterparty" in response.content


def test_betting_boards_link_to_public_house_account() -> None:
    response = Client().get("/bet/")

    assert response.status_code == 200
    assert b'href="/house/"' in response.content
    assert b"Open the House Account" in response.content
