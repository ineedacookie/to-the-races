from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.players.models import Device, Player

COOKIE_SALT = "to-the-races.device.v1"


class GameRequest(HttpRequest):
    game_device: Device | None
    game_player: Player | None
    _game_device_cookie: str
    _dont_enforce_csrf_checks: bool


def _request_api_key(request: HttpRequest) -> str | None:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, credential = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credential:
        return credential.strip()
    header_key = request.headers.get("X-API-Key")
    return header_key.strip() if header_key else None


def encode_device_token(token: uuid.UUID) -> str:
    return signing.dumps(str(token), salt=COOKIE_SALT, compress=True)


def decode_device_token(value: str) -> uuid.UUID | None:
    try:
        raw_token = signing.loads(
            value,
            salt=COOKIE_SALT,
            max_age=settings.DEVICE_COOKIE_MAX_AGE,
        )
        return uuid.UUID(str(raw_token))
    except (signing.BadSignature, ValueError, TypeError):
        return None


def ensure_request_device(request: HttpRequest) -> Device:
    game_request = cast(GameRequest, request)
    existing = getattr(game_request, "game_device", None)
    if isinstance(existing, Device):
        return existing

    device = Device.objects.create()
    game_request.game_device = device
    game_request.game_player = None
    game_request._game_device_cookie = encode_device_token(device.token)
    return device


class DeviceIdentityMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        game_request = cast(GameRequest, request)
        game_request.game_device = None
        game_request.game_player = None

        api_key = _request_api_key(request)
        api_player = Player.objects.filter(api_key=api_key).first() if api_key else None
        if api_key:
            if api_player is not None:
                game_request.game_player = api_player
                if request.path.startswith("/api/"):
                    game_request._dont_enforce_csrf_checks = True
        else:
            cookie = request.COOKIES.get(settings.DEVICE_COOKIE_NAME)
            token = decode_device_token(cookie) if cookie else None
            if token is not None:
                device = Device.objects.select_related("player").filter(token=token).first()
                if device is not None:
                    game_request.game_device = device
                    if device.last_seen_at < timezone.now() - timedelta(minutes=5):
                        Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
                    player = getattr(device, "player", None)
                    if isinstance(player, Player):
                        game_request.game_player = player

        response = self.get_response(request)
        new_cookie = getattr(game_request, "_game_device_cookie", None)
        if isinstance(new_cookie, str):
            response.set_cookie(
                settings.DEVICE_COOKIE_NAME,
                new_cookie,
                max_age=settings.DEVICE_COOKIE_MAX_AGE,
                httponly=True,
                secure=settings.DEVICE_COOKIE_SECURE,
                samesite="Lax",
            )
        return response
