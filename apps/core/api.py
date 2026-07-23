from __future__ import annotations

import json
import uuid
from json import JSONDecodeError
from typing import Any, cast

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.betting.services import BetPlacementError, place_bet
from apps.players.middleware import GameRequest, ensure_request_device
from apps.players.models import Player
from apps.players.names import random_nickname
from apps.players.services import create_player, rename_player
from apps.racing.coordinator import broadcast_current_state
from apps.racing.item_services import ItemDeployError, deploy_item
from apps.racing.seat_services import SeatClaimError, claim_seat
from apps.racing.serializers import build_live_state


def _body(request: HttpRequest) -> dict[str, Any]:
    try:
        parsed = json.loads(request.body or b"{}")
    except JSONDecodeError as error:
        raise ValueError("Request body must be valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object.")
    return parsed


def _validation_message(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        messages = [message for values in error.message_dict.values() for message in values]
        if messages:
            return str(messages[0])
    if error.messages:
        return str(error.messages[0])
    return "The submitted value is not valid."


@require_GET
def state(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    player_id = player.pk if isinstance(player, Player) else None
    return JsonResponse(build_live_state(player_id=player_id))


@require_GET
def nickname_suggestion(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"nickname": random_nickname()})


@require_POST
def identify_player(request: HttpRequest) -> JsonResponse:
    try:
        payload = _body(request)
        requested = payload.get("nickname")
        nickname = requested.strip() if isinstance(requested, str) else None
        device = ensure_request_device(request)
        existing = getattr(request, "game_player", None)
        if isinstance(existing, Player):
            player = rename_player(existing, nickname) if nickname else existing
        else:
            player = create_player(device, nickname)
        cast(GameRequest, request).game_player = player
    except (ValueError, ValidationError) as error:
        message = _validation_message(error) if isinstance(error, ValidationError) else str(error)
        return JsonResponse({"error": {"code": "invalid_nickname", "message": message}}, status=400)

    return JsonResponse(
        {
            "player": {
                "id": player.pk,
                "nickname": player.nickname,
                "balance_cents": player.balance_cents,
            }
        }
    )


@require_POST
def place_player_bet(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        race_entry_id = int(payload["race_entry_id"])
        amount_cents = int(payload["amount_cents"])
        request_id = uuid.UUID(str(payload["client_request_id"]))
        receipt = place_bet(
            player=player,
            race_entry_id=race_entry_id,
            amount_cents=amount_cents,
            client_request_id=request_id,
        )
    except BetPlacementError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    async_to_sync(broadcast_current_state)("bets.updated", include_timeline=False)
    return JsonResponse(
        {
            "bet": {
                "id": receipt.bet_id,
                "amount_cents": receipt.amount_cents,
                "racer_name": receipt.racer_name,
                "odds": receipt.decimal_odds,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        status=200 if receipt.duplicate else 201,
    )


@require_POST
def deploy_round_item(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        round_id = int(payload["round_id"])
        item_slug = str(payload["item_slug"])
        request_id = uuid.UUID(str(payload["client_request_id"]))
        target_entry_id = (
            int(payload["target_entry_id"]) if payload.get("target_entry_id") is not None else None
        )
        track_lane = (
            float(payload["track_lane"]) if payload.get("track_lane") is not None else None
        )
        track_position = (
            float(payload["track_position"])
            if payload.get("track_position") is not None
            else None
        )
        receipt = deploy_item(
            player=player,
            round_id=round_id,
            item_slug=item_slug,
            client_request_id=request_id,
            target_entry_id=target_entry_id,
            track_lane=track_lane,
            track_position=track_position,
        )
    except ItemDeployError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    async_to_sync(broadcast_current_state)("items.updated", include_timeline=False)
    return JsonResponse(
        {
            "item_use": {
                "id": receipt.use_id,
                "item_name": receipt.item_name,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        status=200 if receipt.duplicate else 201,
    )


@require_POST
def claim_round_seat(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        round_id = int(payload["round_id"])
        seat_slug = str(payload["seat_slug"])
        request_id = uuid.UUID(str(payload["client_request_id"]))
        receipt = claim_seat(
            player=player,
            round_id=round_id,
            seat_slug=seat_slug,
            client_request_id=request_id,
        )
    except SeatClaimError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    async_to_sync(broadcast_current_state)("seats.updated", include_timeline=False)
    return JsonResponse(
        {
            "seat_claim": {
                "id": receipt.claim_id,
                "seat_name": receipt.seat_name,
                "seat_color": receipt.seat_color,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        status=200 if receipt.duplicate else 201,
    )
