from __future__ import annotations

from collections.abc import Iterator

import pytest
from apps.realtime.presence import (
    clear_presence,
    connected_spectators,
    register_connection,
    unregister_connection,
)


@pytest.fixture(autouse=True)
def reset_presence() -> Iterator[None]:
    clear_presence()
    yield
    clear_presence()


def test_presence_ref_counts_multiple_tabs_for_one_player() -> None:
    joined = register_connection(
        channel_name="first-tab",
        player_id=7,
        nickname="Double Tab",
        avatar_version="look-a",
    )
    duplicate = register_connection(
        channel_name="second-tab",
        player_id=7,
        nickname="Double Tab",
        avatar_version="look-a",
    )

    assert joined is not None
    assert joined.player_id == 7
    assert duplicate is None
    assert len(connected_spectators()) == 1
    assert unregister_connection(channel_name="first-tab") is None
    assert len(connected_spectators()) == 1
    assert unregister_connection(channel_name="second-tab") == 7
    assert connected_spectators() == []


def test_presence_snapshot_is_stable_and_contains_avatar_assignments() -> None:
    register_connection(
        channel_name="z",
        player_id=2,
        nickname="Zappy",
        avatar_version="zappy-look",
    )
    register_connection(
        channel_name="a",
        player_id=9,
        nickname="Alchemist",
        avatar_version="alchemist-look",
    )

    snapshot = connected_spectators()

    assert [spectator.nickname for spectator in snapshot] == ["Alchemist", "Zappy"]
    assert [spectator.avatar_version for spectator in snapshot] == [
        "alchemist-look",
        "zappy-look",
    ]


def test_unknown_disconnect_is_safe() -> None:
    assert unregister_connection(channel_name="missing") is None
