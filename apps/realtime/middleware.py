from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings

from apps.players.middleware import decode_device_token
from apps.players.models import Device, Player


def _player_for_cookie(cookie_value: str | None) -> Player | None:
    if not cookie_value:
        return None
    token = decode_device_token(cookie_value)
    if token is None:
        return None
    device = Device.objects.select_related("player").filter(token=token).first()
    if device is None:
        return None
    player = getattr(device, "player", None)
    return player if isinstance(player, Player) else None


class DeviceWebSocketMiddleware(BaseMiddleware):
    # types-channels models this runtime-None method as returning an ASGI app.
    async def __call__(  # type: ignore[override]
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        headers = dict(scope.get("headers", []))
        raw_cookie = headers.get(b"cookie", b"").decode("latin-1")
        cookies = SimpleCookie()
        cookies.load(raw_cookie)
        morsel = cookies.get(settings.DEVICE_COOKIE_NAME)
        cookie_value = morsel.value if morsel is not None else None
        scope["game_player"] = await database_sync_to_async(_player_for_cookie)(cookie_value)
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]
