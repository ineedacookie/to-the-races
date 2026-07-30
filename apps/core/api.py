from __future__ import annotations

import uuid
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_GET, require_POST

from apps.betting.bailout_services import patch_bailout_wound, start_bailout
from apps.betting.services import place_bet
from apps.core.action_handlers import error_response, player_action, request_body
from apps.players.avatar import (
    avatar_version,
    normalize_avatar_recipe,
    render_avatar_png,
)
from apps.players.middleware import GameRequest, ensure_request_device
from apps.players.models import Player
from apps.players.names import random_nickname
from apps.players.serialization import player_identity_fields
from apps.players.services import (
    PlayerLoginError,
    create_player,
    login_player,
    update_player_identity,
    update_replay_preference,
)
from apps.racing.coordinator import regenerate_live_race
from apps.racing.item_services import (
    ItemUseReceipt,
    discard_inventory_item,
    purchase_item,
    use_inventory_item,
)
from apps.racing.models import RoomSettings, Round
from apps.racing.seat_services import claim_seat
from apps.racing.serializers import build_live_state
from apps.racing.upgrade_services import purchase_upgrade


def _validation_message(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        messages = [message for values in error.message_dict.values() for message in values]
        if messages:
            return str(messages[0])
    if error.messages:
        return str(error.messages[0])
    return "The submitted value is not valid."


def _player_identity_response(player: Player) -> JsonResponse:
    return JsonResponse({"player": player_identity_fields(player)})


def _request_id(payload: dict[str, Any]) -> uuid.UUID:
    return uuid.UUID(str(payload["client_request_id"]))


def _use_item(player: Player, payload: dict[str, Any]) -> ItemUseReceipt:
    round_id = int(payload["round_id"])
    with transaction.atomic():
        # Match the coordinator's room-then-round lock order.
        RoomSettings.objects.select_for_update().get_or_create(pk=1)
        receipt = use_inventory_item(
            player=player,
            round_id=round_id,
            inventory_item_id=int(payload["inventory_item_id"]),
            target_entry_id=int(payload["target_entry_id"]),
            client_request_id=_request_id(payload),
        )
        if receipt.live_activation and not receipt.duplicate:
            regenerate_live_race(round_id)
    return receipt


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
        payload = request_body(request)
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
        payload = request_body(request)
        requested = payload.get("nickname")
        if not isinstance(requested, str):
            raise PlayerLoginError("Enter an existing username.")
        device = ensure_request_device(request)
        player = login_player(device, requested)
        cast(GameRequest, request).game_player = player
    except ValueError as error:
        return error_response("invalid_request", str(error), status=400)
    except PlayerLoginError as error:
        return error_response("player_not_found", str(error), status=404)

    return _player_identity_response(player)


@require_POST
def player_replay_preference(request: HttpRequest) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return error_response(
            "identity_required",
            "Choose a nickname first.",
            status=401,
        )
    try:
        payload = request_body(request)
        requested = payload.get("preference")
        if not isinstance(requested, str):
            raise ValueError("Choose ask, always_watch, or always_skip.")
        player = update_replay_preference(player, requested)
        cast(GameRequest, request).game_player = player
    except (KeyError, TypeError, ValueError) as error:
        return error_response("invalid_replay_preference", str(error), status=400)
    return JsonResponse(
        {
            "player": {
                "replay_preference": player.replay_preference,
            }
        }
    )


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


@require_GET
def round_replay(request: HttpRequest, round_id: int) -> JsonResponse:
    player = getattr(request, "game_player", None)
    if not isinstance(player, Player):
        return error_response(
            "identity_required",
            "Choose a nickname first.",
            status=401,
        )
    current_round = (
        Round.objects.select_related("race")
        .filter(pk=round_id)
        .first()
    )
    montage = current_round.race.replay_montage if current_round is not None else {}
    clips = montage.get("clips") if isinstance(montage, dict) else None
    if (
        current_round is None
        or current_round.state != Round.State.RESULTS
        or current_round.results_end_at <= timezone.now()
        or not isinstance(clips, list)
        or not clips
    ):
        return error_response(
            "replay_unavailable",
            "That instant replay is no longer available.",
            status=409,
        )
    return JsonResponse({"replay": montage})


@require_POST
def place_player_bet(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: place_bet(
            player=player,
            race_entry_id=int(payload["race_entry_id"]),
            amount_cents=int(payload["amount_cents"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "bet": {
                "id": receipt.bet_id,
                "amount_cents": receipt.amount_cents,
                "racer_name": receipt.racer_name,
                "odds": receipt.decimal_odds,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="bets.updated",
    )


@require_POST
def purchase_player_item(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: purchase_item(
            player=player,
            item_slug=str(payload["item_slug"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "inventory_item": {
                "id": receipt.inventory_item_id,
                "item_name": receipt.item_name,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="items.updated",
    )


@require_POST
def discard_player_item(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: discard_inventory_item(
            player=player,
            inventory_item_id=int(payload["inventory_item_id"]),
        ),
        serialize=lambda receipt: {
            "discarded_item": {
                "id": receipt.inventory_item_id,
                "item_name": receipt.item_name,
                "duplicate": receipt.duplicate,
            },
        },
        created_status=None,
        broadcast_event="items.updated",
    )


@require_POST
def use_player_item(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=_use_item,
        serialize=lambda receipt: {
            "item_use": {
                "id": receipt.use_id,
                "inventory_item_id": receipt.inventory_item_id,
                "item_name": receipt.item_name,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="items.updated",
        include_timeline=lambda receipt: receipt.live_activation,
    )


@require_POST
def purchase_player_upgrade(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: purchase_upgrade(
            player=player,
            upgrade_slug=str(payload["upgrade_slug"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "player_upgrade": {
                "id": receipt.player_upgrade_id,
                "upgrade_name": receipt.upgrade_name,
                "inventory_capacity": receipt.inventory_capacity,
                "price_paid_cents": receipt.price_paid_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="upgrades.updated",
    )


@require_POST
def claim_round_seat(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: claim_seat(
            player=player,
            round_id=int(payload["round_id"]),
            seat_slug=str(payload["seat_slug"]),
            expected_price_cents=int(payload["expected_price_cents"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "seat_claim": {
                "id": receipt.claim_id,
                "seat_name": receipt.seat_name,
                "seat_color": receipt.seat_color,
                "price_paid_cents": receipt.price_paid_cents,
                "next_price_cents": receipt.next_price_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="seats.updated",
    )


@require_POST
def start_track_medic_bailout(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: start_bailout(
            player=player,
            round_id=int(payload["round_id"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "bailout": {
                "session_id": receipt.session_id,
                "round_id": receipt.round_id,
                "race_entry_id": receipt.race_entry_id,
                "racer_name": receipt.racer_name,
                "sprite_key": receipt.sprite_key,
                "wound_count": receipt.wound_count,
                "wounds": receipt.wounds,
                "patched_indices": receipt.patched_indices,
                "completed": receipt.completed,
                "reward_cents": receipt.reward_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="bailout.updated",
    )


@require_POST
def patch_track_medic_wound(request: HttpRequest) -> JsonResponse:
    return player_action(
        request,
        execute=lambda player, payload: patch_bailout_wound(
            player=player,
            session_id=int(payload["session_id"]),
            wound_index=int(payload["wound_index"]),
            client_request_id=_request_id(payload),
        ),
        serialize=lambda receipt: {
            "bailout_patch": {
                "session_id": receipt.session_id,
                "wound_index": receipt.wound_index,
                "patched_indices": receipt.patched_indices,
                "completed": receipt.completed,
                "reward_cents": receipt.reward_cents,
                "duplicate": receipt.duplicate,
            },
            "balance_cents": receipt.balance_cents,
        },
        broadcast_event="bailout.updated",
    )
