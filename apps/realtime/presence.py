from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class ConnectedSpectatorPayload(TypedDict):
    player_id: int
    nickname: str
    avatar_version: str


@dataclass(frozen=True, slots=True)
class ConnectedSpectator:
    player_id: int
    nickname: str
    avatar_version: str

    def payload(self) -> ConnectedSpectatorPayload:
        return {
            "player_id": self.player_id,
            "nickname": self.nickname,
            "avatar_version": self.avatar_version,
        }


@dataclass(slots=True)
class _PresenceEntry:
    spectator: ConnectedSpectator
    channel_names: set[str]


_channels: dict[str, int] = {}
_players: dict[int, _PresenceEntry] = {}


def _spectator(
    *,
    player_id: int,
    nickname: str,
    avatar_version: str,
) -> ConnectedSpectator:
    return ConnectedSpectator(
        player_id=player_id,
        nickname=nickname,
        avatar_version=avatar_version,
    )


def register_connection(
    *,
    channel_name: str,
    player_id: int,
    nickname: str,
    avatar_version: str,
) -> ConnectedSpectator | None:
    previous_player_id = _channels.get(channel_name)
    if previous_player_id == player_id:
        return None
    if previous_player_id is not None:
        unregister_connection(channel_name=channel_name)

    spectator = _spectator(
        player_id=player_id,
        nickname=nickname,
        avatar_version=avatar_version,
    )
    entry = _players.get(player_id)
    first_connection = entry is None
    changed = False
    if entry is None:
        entry = _PresenceEntry(spectator=spectator, channel_names=set())
        _players[player_id] = entry
    else:
        changed = entry.spectator != spectator
        entry.spectator = spectator

    entry.channel_names.add(channel_name)
    _channels[channel_name] = player_id
    return spectator if first_connection or changed else None


def unregister_connection(*, channel_name: str) -> int | None:
    player_id = _channels.pop(channel_name, None)
    if player_id is None:
        return None

    entry = _players.get(player_id)
    if entry is None:
        return None
    entry.channel_names.discard(channel_name)
    if entry.channel_names:
        return None

    del _players[player_id]
    return player_id


def connected_spectators() -> list[ConnectedSpectator]:
    return sorted(
        (entry.spectator for entry in _players.values()),
        key=lambda spectator: (spectator.nickname.casefold(), spectator.player_id),
    )


def clear_presence() -> None:
    _channels.clear()
    _players.clear()
