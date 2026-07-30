from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_persistent_seat_migration_preserves_history_and_one_seat_per_player() -> None:
    migrate_from = ("racing", "0011_upgradeddefinition_playerupgrade")
    migrate_to = ("racing", "0012_persistent_seat_ownership")
    players_at_migration = ("players", "0004_player_balance_non_negative")
    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from, players_at_migration])
    old_apps = executor.loader.project_state([migrate_from, players_at_migration]).apps

    Player = old_apps.get_model("players", "Player")
    Round = old_apps.get_model("racing", "Round")
    RoundSeatClaim = old_apps.get_model("racing", "RoundSeatClaim")
    Seat = old_apps.get_model("racing", "SpectatorSeatDefinition")

    first_player = Player.objects.create(nickname="Migrating A", balance_cents=10_000)
    second_player = Player.objects.create(nickname="Migrating B", balance_cents=10_000)
    first_seat = Seat.objects.create(
        slug="migration-seat-one",
        name="Migration Seat One",
        description="First migration seat",
        color="#112233",
        price_cents=4_000,
        sort_order=1,
    )
    second_seat = Seat.objects.create(
        slug="migration-seat-two",
        name="Migration Seat Two",
        description="Second migration seat",
        color="#334455",
        price_cents=6_000,
        sort_order=2,
    )
    now = timezone.now()
    rounds = [
        Round.objects.create(
            number=index,
            state="results" if index < 3 else "open",
            opened_at=now + timedelta(minutes=index),
            locks_at=now + timedelta(minutes=index, seconds=30),
            race_starts_at=now + timedelta(minutes=index, seconds=31),
            race_ends_at=now + timedelta(minutes=index, seconds=50),
            results_end_at=now + timedelta(minutes=index, seconds=55),
        )
        for index in range(1, 4)
    ]
    claims = [
        RoundSeatClaim.objects.create(
            player=second_player,
            round=rounds[0],
            seat=first_seat,
            price_paid_cents=4_000,
            client_request_id=uuid.uuid4(),
        ),
        RoundSeatClaim.objects.create(
            player=first_player,
            round=rounds[1],
            seat=first_seat,
            price_paid_cents=4_500,
            client_request_id=uuid.uuid4(),
        ),
        RoundSeatClaim.objects.create(
            player=first_player,
            round=rounds[2],
            seat=second_seat,
            price_paid_cents=6_000,
            client_request_id=uuid.uuid4(),
        ),
    ]
    for index, claim in enumerate(claims):
        RoundSeatClaim.objects.filter(pk=claim.pk).update(
            created_at=now + timedelta(minutes=index),
        )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to, players_at_migration])
    new_apps = executor.loader.project_state([migrate_to, players_at_migration]).apps
    Ownership = new_apps.get_model("racing", "SeatOwnership")
    Receipt = new_apps.get_model("racing", "SeatTakeoverReceipt")

    ownerships = set(Ownership.objects.values_list("seat_id", "player_id"))
    assert ownerships == {
        (first_seat.pk, second_player.pk),
        (second_seat.pk, first_player.pk),
    }
    assert list(Receipt.objects.values_list("player_id", flat=True)) == [
        second_player.pk,
        first_player.pk,
        first_player.pk,
    ]
    assert Receipt.objects.filter(previous_owner_id=second_player.pk).count() == 1

    final_takeover = Receipt.objects.create(
        player_id=second_player.pk,
        round_id=rounds[2].pk,
        seat_id=second_seat.pk,
        previous_owner_id=first_player.pk,
        price_paid_cents=6_500,
        client_request_id=uuid.uuid4(),
    )
    Receipt.objects.filter(pk=final_takeover.pk).update(
        created_at=now + timedelta(minutes=4),
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from, players_at_migration])
    rolled_back_apps = executor.loader.project_state([migrate_from, players_at_migration]).apps
    RestoredClaim = rolled_back_apps.get_model("racing", "RoundSeatClaim")
    restored = RestoredClaim.objects.get(round_id=rounds[2].pk, seat_id=second_seat.pk)
    assert restored.player_id == second_player.pk
    assert restored.price_paid_cents == 6_500

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
