from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.players.avatar import avatar_version, normalize_avatar_recipe
from apps.players.models import Player
from apps.racing.coordinator import DISPLAY_GROUP, LIVE_GROUP
from apps.racing.models import RaceEntry, Round, SeatOwnership
from apps.racing.serializers import build_live_state
from apps.realtime.audience import AudienceValidationError, parse_audience_reaction
from apps.realtime.presence import (
    connected_spectators,
    register_connection,
    unregister_connection,
)

REACTION_COOLDOWN_SECONDS = 3.0


class LiveGameConsumer(AsyncJsonWebsocketConsumer):
    role: str
    player: Player | None
    groups_to_leave: list[str]
    last_reaction_at: float

    async def connect(self) -> None:
        query = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        self.role = query.get("role", ["bet"])[0]
        scoped_player = self.scope.get("game_player")
        self.player = scoped_player if isinstance(scoped_player, Player) else None
        self.groups_to_leave = []
        self.last_reaction_at = 0.0

        group = DISPLAY_GROUP if self.role == "display" else LIVE_GROUP
        if self.channel_layer is not None:
            await self.channel_layer.group_add(group, self.channel_name)
            self.groups_to_leave.append(group)
            if self.player is not None:
                player_group = f"player_{self.player.pk}"
                await self.channel_layer.group_add(player_group, self.channel_name)
                self.groups_to_leave.append(player_group)

        await self.accept()
        joined_payload: dict[str, object] | None = None
        if self.role == "bet" and self.player is not None:
            player_avatar = normalize_avatar_recipe(
                self.player.avatar_recipe,
                seed=self.player.pk,
            )
            joined = register_connection(
                channel_name=self.channel_name,
                player_id=self.player.pk,
                nickname=self.player.nickname,
                avatar_version=avatar_version(player_avatar),
            )
            if joined is not None:
                joined_payload = {
                    "type": "presence.join",
                    "spectator": joined.payload(),
                }
        await self._send_sync()
        if joined_payload is not None:
            await self._broadcast_presence(joined_payload)
        if self.role == "display":
            await self.send_json(
                {
                    "type": "presence.sync",
                    "spectators": [spectator.payload() for spectator in connected_spectators()],
                }
            )

    async def disconnect(self, close_code: int) -> None:
        left_player_id = unregister_connection(channel_name=self.channel_name)
        if left_player_id is not None:
            await self._broadcast_presence(
                {
                    "type": "presence.leave",
                    "player_id": left_player_id,
                }
            )
        if self.channel_layer is not None:
            for group in self.groups_to_leave:
                await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        message_type = content.get("type") if isinstance(content, dict) else None
        if message_type == "sync.request":
            await self._send_sync()
        elif message_type == "ping":
            await self.send_json({"type": "pong"})
        elif message_type == "audience.react":
            await self._handle_audience_reaction(content if isinstance(content, dict) else {})

    async def game_message(self, event: dict[str, Any]) -> None:
        payload = event["payload"]
        if self.role == "bet" and isinstance(payload.get("state"), dict):
            state = await database_sync_to_async(build_live_state)(
                player_id=self.player.pk if self.player is not None else None,
                include_timeline=False,
            )
            payload = {**payload, "state": state}
        await self.send_json(payload)

    async def _send_sync(self) -> None:
        state = await database_sync_to_async(build_live_state)(
            player_id=self.player.pk if self.player is not None else None,
            include_timeline=self.role == "display",
        )
        await self.send_json({"type": "state.sync", "state": state})

    async def _handle_audience_reaction(self, payload: dict[str, object]) -> None:
        if self.role != "bet" or self.player is None:
            await self.send_json(
                {
                    "type": "audience.rejected",
                    "message": "Only authenticated bet clients can react.",
                }
            )
            return

        now = time.monotonic()
        if now - self.last_reaction_at < REACTION_COOLDOWN_SECONDS:
            await self.send_json(
                {
                    "type": "audience.rejected",
                    "message": "Slow down — reactions stay up for three seconds.",
                }
            )
            return

        try:
            reaction = parse_audience_reaction(payload)
        except AudienceValidationError as error:
            await self.send_json({"type": "audience.rejected", "message": str(error)})
            return

        seat_name: str | None = None
        seat_color: str | None = None
        if reaction.racer_id is not None:
            valid = await database_sync_to_async(self._racer_in_current_round)(reaction.racer_id)
            if not valid:
                await self.send_json(
                    {
                        "type": "audience.rejected",
                        "message": "That racer is not in the current round.",
                    }
                )
                return

        seat = await database_sync_to_async(self._current_seat_ownership)()
        if seat is not None:
            seat_name = seat.seat.name
            seat_color = seat.seat.color

        self.last_reaction_at = now
        event_payload: dict[str, object] = {
            "type": "audience.reaction",
            "reaction": {
                "player_id": self.player.pk,
                "nickname": self.player.nickname,
                "kind": reaction.kind,
                "text": reaction.text,
                "racer_id": reaction.racer_id,
                "seat_name": seat_name or "",
                "seat_color": seat_color or "#f3bc3e",
                "display_ms": round(REACTION_COOLDOWN_SECONDS * 1_000),
                "at": timezone.now().isoformat(),
            },
        }
        await self._broadcast_audience(event_payload)

    def _racer_in_current_round(self, racer_id: int) -> bool:
        current_round = Round.objects.select_related("race").order_by("-number").first()
        if current_round is None:
            return False
        return RaceEntry.objects.filter(race=current_round.race, racer_id=racer_id).exists()

    def _current_seat_ownership(self) -> SeatOwnership | None:
        if self.player is None:
            return None
        return SeatOwnership.objects.filter(player=self.player).select_related("seat").first()

    async def _broadcast_audience(self, payload: dict[str, object]) -> None:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        for group in (LIVE_GROUP, DISPLAY_GROUP):
            await channel_layer.group_send(
                group,
                {
                    "type": "game.message",
                    "payload": payload,
                },
            )

    async def _broadcast_presence(self, payload: dict[str, object]) -> None:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        for group in (LIVE_GROUP, DISPLAY_GROUP):
            await channel_layer.group_send(
                group,
                {
                    "type": "game.message",
                    "payload": payload,
                },
            )
