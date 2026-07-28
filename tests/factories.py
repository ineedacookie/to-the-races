from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from apps.racing.models import Race, RaceEntry, Racer, RoomSettings, Round
from apps.racing.seat_services import ensure_round_seat_markets
from django.core.management import call_command
from django.utils import timezone


def seed_catalog() -> None:
    call_command("seed_game")


def open_round_with_entries(
    *,
    use_catalog: bool = False,
    create_seat_markets: bool = False,
    opening_balance_cents: int | None = None,
    max_round_stake_cents: int | None = None,
    second_odds: str = "4.00",
) -> tuple[Round, RaceEntry, RaceEntry]:
    if use_catalog:
        seed_catalog()

    if opening_balance_cents is not None or max_round_stake_cents is not None:
        room = RoomSettings.load()
        if opening_balance_cents is not None:
            room.opening_balance_cents = opening_balance_cents
        if max_round_stake_cents is not None:
            room.max_round_stake_cents = max_round_stake_cents
        room.save()

    now = timezone.now()
    current_round = Round.objects.create(
        number=1,
        state=Round.State.OPEN,
        opened_at=now,
        locks_at=now + timedelta(minutes=1),
        race_starts_at=now + timedelta(minutes=2),
        race_ends_at=now + timedelta(minutes=3),
        results_end_at=now + timedelta(minutes=4),
    )
    race = Race.objects.create(round=current_round)
    if use_catalog:
        racers = list(Racer.objects.filter(active=True).order_by("sort_order")[:2])
    else:
        racers = [
            Racer.objects.create(name="First", slug="first", sprite_key="first"),
            Racer.objects.create(name="Second", slug="second", sprite_key="second"),
        ]
    first = RaceEntry.objects.create(
        race=race,
        racer=racers[0],
        lane=1,
        odds=Decimal("3.00"),
    )
    second = RaceEntry.objects.create(
        race=race,
        racer=racers[1],
        lane=2,
        odds=Decimal(second_odds),
    )
    if create_seat_markets:
        ensure_round_seat_markets(current_round)
    return current_round, first, second
