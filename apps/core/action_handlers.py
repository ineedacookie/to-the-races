from __future__ import annotations

import json
from collections.abc import Callable
from json import JSONDecodeError
from typing import Any, Protocol

from asgiref.sync import async_to_sync
from django.http import HttpRequest, JsonResponse

from apps.core.errors import ServiceError
from apps.players.models import Player
from apps.racing.coordinator import broadcast_current_state


class _ActionReceipt(Protocol):
    @property
    def duplicate(self) -> bool: ...


def request_body(request: HttpRequest) -> dict[str, Any]:
    try:
        parsed = json.loads(request.body or b"{}")
    except JSONDecodeError as error:
        raise ValueError("Request body must be valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object.")
    return parsed


def error_response(code: str, message: str, *, status: int) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": code, "message": message}},
        status=status,
    )


def player_action[ReceiptT: _ActionReceipt](
    request: HttpRequest,
    *,
    execute: Callable[[Player, dict[str, Any]], ReceiptT],
    serialize: Callable[[ReceiptT], dict[str, Any]],
    created_status: int | None = 201,
    broadcast_event: str | None = None,
    include_timeline: bool | Callable[[ReceiptT], bool] = False,
) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return error_response(
            "identity_required",
            "Choose a nickname first.",
            status=401,
        )

    try:
        receipt = execute(player, request_body(request))
    except ServiceError as error:
        return error_response(error.code, str(error), status=409)
    except (KeyError, TypeError, ValueError) as error:
        return error_response("invalid_request", str(error), status=400)

    if broadcast_event is not None:
        timeline = (
            include_timeline(receipt) if callable(include_timeline) else include_timeline
        )
        async_to_sync(broadcast_current_state)(
            broadcast_event,
            include_timeline=timeline,
        )

    status = 200 if created_status is None or receipt.duplicate else created_status
    return JsonResponse(serialize(receipt), status=status)
