from __future__ import annotations

import json
import uuid
from json import JSONDecodeError
from typing import Any, cast

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_GET, require_POST

from apps.betting.services import BetPlacementError, place_bet
from apps.players.avatar import (
    avatar_version,
    normalize_avatar_recipe,
    render_avatar_png,
)
from apps.players.middleware import GameRequest, ensure_request_device
from apps.players.models import Player
from apps.players.names import random_nickname
from apps.players.services import (
    PlayerLoginError,
    create_player,
    login_player,
    update_player_identity,
)
from apps.racing.coordinator import broadcast_current_state, regenerate_live_race
from apps.racing.item_services import (
    ItemActionError,
    discard_inventory_item,
    purchase_item,
    use_inventory_item,
)
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


def _player_identity_response(player: Player) -> JsonResponse:
    recipe = normalize_avatar_recipe(player.avatar_recipe, seed=player.pk)
    version = avatar_version(recipe)
    return JsonResponse(
        {
            "player": {
                "id": player.pk,
                "nickname": player.nickname,
                "balance_cents": player.balance_cents,
                "avatar_version": version,
                "avatar_url": f"/api/players/{player.pk}/avatar/?v={version}",
            }
        }
    )


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
        avatar_recipe = payload.get("avatar") if "avatar" in payload else None
        device = ensure_request_device(request)
        existing = getattr(request, "game_player", None)
        if isinstance(existing, Player):
            player = (
                update_player_identity(
                    existing,
                    nickname=nickname,
                    avatar_recipe=avatar_recipe,
                )
                if nickname or avatar_recipe is not None
                else existing
            )
        else:
            player = create_player(device, nickname, avatar_recipe)
        cast(GameRequest, request).game_player = player
    except (ValueError, ValidationError) as error:
        message = _validation_message(error) if isinstance(error, ValidationError) else str(error)
        code = (
            "invalid_avatar"
            if isinstance(error, ValidationError)
            and hasattr(error, "message_dict")
            and "avatar" in error.message_dict
            else "invalid_nickname"
        )
        return JsonResponse({"error": {"code": code, "message": message}}, status=400)

    return _player_identity_response(player)


@require_POST
def login_existing_player(request: HttpRequest) -> JsonResponse:
    try:
        payload = _body(request)
        requested = payload.get("nickname")
        if not isinstance(requested, str):
            raise PlayerLoginError("Enter an existing username.")
        device = ensure_request_device(request)
        player = login_player(device, requested)
        cast(GameRequest, request).game_player = player
    except ValueError as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )
    except PlayerLoginError as error:
        return JsonResponse(
            {"error": {"code": "player_not_found", "message": str(error)}},
            status=404,
        )

    return _player_identity_response(player)


@require_GET
def player_avatar(request: HttpRequest, player_id: int) -> HttpResponse:
    player = get_object_or_404(Player.objects.only("pk", "avatar_recipe"), pk=player_id)
    recipe = normalize_avatar_recipe(player.avatar_recipe, seed=player.pk)
    version = avatar_version(recipe)
    etag = f'"{version}"'
    if request.headers.get("If-None-Match") == etag:
        return HttpResponseNotModified()

    response = HttpResponse(render_avatar_png(recipe), content_type="image/png")
    response.headers["ETag"] = etag
    patch_cache_control(
        response,
        public=True,
        max_age=31_536_000,
        immutable=True,
    )
    return response


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
def purchase_player_item(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        item_slug = str(payload["item_slug"])
        request_id = uuid.UUID(str(payload["client_request_id"]))
        receipt = purchase_item(
            player=player,
            item_slug=item_slug,
            client_request_id=request_id,
        )
    except ItemActionError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    return JsonResponse(
        {
            "inventory_item": {
                "id": receipt.inventory_item_id,
                "item_name": receipt.item_name,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        status=200 if receipt.duplicate else 201,
    )


@require_POST
def discard_player_item(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        inventory_item_id = int(payload["inventory_item_id"])
        receipt = discard_inventory_item(
            player=player,
            inventory_item_id=inventory_item_id,
        )
    except ItemActionError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    return JsonResponse(
        {
            "discarded_item": {
                "id": receipt.inventory_item_id,
                "item_name": receipt.item_name,
                "duplicate": receipt.duplicate,
            },
        }
    )


@require_POST
def use_player_item(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return JsonResponse(
            {"error": {"code": "identity_required", "message": "Choose a nickname first."}},
            status=401,
        )

    try:
        payload = _body(request)
        round_id = int(payload["round_id"])
        inventory_item_id = int(payload["inventory_item_id"])
        target_entry_id = int(payload["target_entry_id"])
        request_id = uuid.UUID(str(payload["client_request_id"]))
        with transaction.atomic():
            receipt = use_inventory_item(
                player=player,
                round_id=round_id,
                inventory_item_id=inventory_item_id,
                target_entry_id=target_entry_id,
                client_request_id=request_id,
            )
            if receipt.live_activation and not receipt.duplicate:
                regenerate_live_race(round_id)
    except ItemActionError as error:
        return JsonResponse(
            {"error": {"code": error.code, "message": str(error)}},
            status=409,
        )
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse(
            {"error": {"code": "invalid_request", "message": str(error)}},
            status=400,
        )

    async_to_sync(broadcast_current_state)(
        "items.updated",
        include_timeline=receipt.live_activation,
    )
    return JsonResponse(
        {
            "item_use": {
                "id": receipt.use_id,
                "inventory_item_id": receipt.inventory_item_id,
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
