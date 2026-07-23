from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.betting.models import Bet, LedgerEntry
from apps.players.models import Player
from apps.racing.models import (
    ItemDefinition,
    RaceEntry,
    RoomSettings,
    Round,
    RoundItemUse,
    RoundSeatClaim,
    SpectatorSeatDefinition,
)


def _timestamp(value: object) -> str | None:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return None


def _race_tick_timestamp(
    start: datetime,
    tick: object,
    tick_rate: int,
) -> str | None:
    if type(tick) is not int or tick_rate <= 0:
        return None
    return _timestamp(start + timedelta(seconds=tick / tick_rate))


def _item_catalog() -> list[dict[str, Any]]:
    return [
        {
            "slug": item.slug,
            "name": item.name,
            "description": item.description,
            "icon": item.icon,
            "color": item.color,
            "kind": item.kind,
            "target": item.target,
            "price_cents": item.price_cents,
            "effect_strength": item.effect_strength,
        }
        for item in ItemDefinition.objects.filter(active=True)
    ]


def _seat_catalog() -> list[dict[str, Any]]:
    return [
        {
            "slug": seat.slug,
            "name": seat.name,
            "description": seat.description,
            "sprite_key": seat.sprite_key,
            "color": seat.color,
            "price_cents": seat.price_cents,
        }
        for seat in SpectatorSeatDefinition.objects.filter(active=True)
    ]


def _serialize_item_use(use: RoundItemUse) -> dict[str, Any]:
    return {
        "id": use.pk,
        "buyer": use.player.nickname,
        "item_slug": use.item.slug,
        "item_name": use.item.name,
        "item_icon": use.item.icon,
        "item_color": use.item.color,
        "kind": use.item.kind,
        "target_entry_id": use.target_entry_id,
        "target_racer_id": (
            use.target_entry.racer_id if use.target_entry is not None else None
        ),
        "target_racer_name": (
            use.target_entry.racer.name if use.target_entry is not None else None
        ),
        "track_lane": use.track_lane,
        "track_position": use.track_position,
        "price_paid_cents": use.price_paid_cents,
        "created_at": _timestamp(use.created_at),
    }


def _serialize_seat_claim(claim: RoundSeatClaim) -> dict[str, Any]:
    return {
        "id": claim.pk,
        "seat_slug": claim.seat.slug,
        "seat_name": claim.seat.name,
        "seat_description": claim.seat.description,
        "sprite_key": claim.seat.sprite_key,
        "seat_color": claim.seat.color,
        "price_paid_cents": claim.price_paid_cents,
        "nickname": claim.player.nickname,
        "created_at": _timestamp(claim.created_at),
    }


def _leaderboard(limit: int = 8) -> list[dict[str, Any]]:
    players = (
        Player.objects.filter(balance_cents__gte=0)
        .annotate(
            total_bets=Count("bets"),
            wins=Count("bets", filter=Q(bets__status=Bet.Status.WON)),
        )
        .order_by("-balance_cents", "nickname")[:limit]
    )
    return [
        {
            "rank": index,
            "player_id": player.pk,
            "nickname": player.nickname,
            "balance_cents": player.balance_cents,
            "total_bets": player.total_bets,
            "wins": player.wins,
        }
        for index, player in enumerate(players, start=1)
    ]


def _debt_board(limit: int = 8) -> list[dict[str, Any]]:
    players = (
        Player.objects.filter(balance_cents__lt=0)
        .annotate(
            total_bets=Count("bets"),
            wins=Count("bets", filter=Q(bets__status=Bet.Status.WON)),
        )
        .order_by("balance_cents", "nickname")[:limit]
    )
    return [
        {
            "rank": index,
            "player_id": player.pk,
            "nickname": player.nickname,
            "balance_cents": player.balance_cents,
            "total_bets": player.total_bets,
            "wins": player.wins,
        }
        for index, player in enumerate(players, start=1)
    ]


def build_live_state(
    *,
    player_id: int | None = None,
    include_timeline: bool = False,
) -> dict[str, Any]:
    room = RoomSettings.load()
    current_round = Round.objects.select_related("race").order_by("-number").first()
    payload: dict[str, Any] = {
        "protocol_version": 4,
        "server_time": timezone.now().isoformat(),
        "room": {
            "name": room.name,
            "is_paused": room.is_paused,
            "max_round_stake_cents": room.max_round_stake_cents,
            "max_round_item_spend_cents": room.max_round_item_spend_cents,
            "max_round_item_uses": room.max_round_item_uses,
            "item_catalog": _item_catalog(),
            "seat_catalog": _seat_catalog(),
        },
        "leaderboard": _leaderboard(),
        "debt_board": _debt_board(),
        "round": None,
        "player": None,
    }
    player = Player.objects.filter(pk=player_id).first() if player_id is not None else None
    if player is not None:
        payload["player"] = {
            "id": player.pk,
            "nickname": player.nickname,
            "balance_cents": player.balance_cents,
            "round_staked_cents": 0,
            "round_item_spent_cents": 0,
            "item_uses": [],
            "bets": [],
            "seat_claim": None,
            "recent_ledger": [],
        }
    if current_round is None:
        return payload

    entries = list(
        RaceEntry.objects.filter(race=current_round.race)
        .select_related("racer")
        .order_by("lane")
    )
    totals: defaultdict[int, int] = defaultdict(int)
    for entry_id, amount_cents in (
        Bet.objects.filter(round=current_round)
        .values_list("race_entry_id", "amount_cents")
        .iterator()
    ):
        totals[entry_id] += amount_cents

    item_uses = list(
        RoundItemUse.objects.filter(round=current_round)
        .select_related("player", "item", "target_entry__racer")
        .order_by("created_at", "pk")
    )
    seat_claims = list(
        RoundSeatClaim.objects.filter(round=current_round)
        .select_related("player", "seat")
        .order_by("created_at", "pk")
    )
    results_visible = current_round.state == Round.State.RESULTS
    race_result = current_round.race.result or {}
    finish_countdown_starts_at = _race_tick_timestamp(
        current_round.race_starts_at,
        race_result.get("first_finish_tick"),
        current_round.race.tick_rate,
    )
    finish_countdown_ends_at = _race_tick_timestamp(
        current_round.race_starts_at,
        race_result.get("finish_deadline_tick"),
        current_round.race.tick_rate,
    )

    round_payload: dict[str, Any] = {
        "id": current_round.pk,
        "number": current_round.number,
        "state": current_round.state,
        "opened_at": _timestamp(current_round.opened_at),
        "locks_at": _timestamp(current_round.locks_at),
        "race_starts_at": _timestamp(current_round.race_starts_at),
        "race_ends_at": _timestamp(current_round.race_ends_at),
        "results_end_at": _timestamp(current_round.results_end_at),
        "finish_countdown_starts_at": finish_countdown_starts_at,
        "finish_countdown_ends_at": finish_countdown_ends_at,
        "entries": [
            {
                "id": entry.pk,
                "racer_id": entry.racer_id,
                "name": entry.racer.name,
                "slug": entry.racer.slug,
                "sprite_key": entry.racer.sprite_key,
                "color": entry.racer.color,
                "tagline": entry.racer.tagline,
                "backstory": entry.racer.backstory,
                "lane": entry.lane,
                "odds": str(entry.odds),
                "total_staked_cents": totals[entry.pk],
                "finish_place": entry.finish_place if results_visible else None,
                "dnf_reason": entry.dnf_reason if results_visible else "",
            }
            for entry in entries
        ],
        "item_uses": [_serialize_item_use(use) for use in item_uses],
        "seats": [_serialize_seat_claim(claim) for claim in seat_claims],
        "result": race_result if results_visible else {},
    }
    if include_timeline and current_round.race.timeline:
        race_inputs = current_round.race.inputs or {}
        round_payload["race"] = {
            "seed": current_round.race.seed,
            "tick_rate": current_round.race.tick_rate,
            "duration_ticks": current_round.race.duration_ticks,
            "timeline": current_round.race.timeline,
            "events": current_round.race.events,
            "effects": race_inputs.get("effects", []),
            "successful_effect_ids": race_inputs.get("successful_effect_ids", []),
            "failed_effect_ids": race_inputs.get("failed_effect_ids", []),
        }
    payload["round"] = round_payload

    if player is not None:
        player_bets = Bet.objects.filter(player=player, round=current_round).select_related(
            "race_entry__racer"
        )
        player_item_uses = [use for use in item_uses if use.player_id == player.pk]
        player_seat = next((claim for claim in seat_claims if claim.player_id == player.pk), None)
        recent_ledger = LedgerEntry.objects.filter(player=player).order_by("-created_at", "-pk")[:8]
        payload["player"] = {
            "id": player.pk,
            "nickname": player.nickname,
            "balance_cents": player.balance_cents,
            "round_staked_cents": sum(bet.amount_cents for bet in player_bets),
            "round_item_spent_cents": sum(use.price_paid_cents for use in player_item_uses),
            "item_uses": [_serialize_item_use(use) for use in player_item_uses],
            "bets": [
                {
                    "id": bet.pk,
                    "racer_name": bet.race_entry.racer.name,
                    "racer_id": bet.race_entry.racer_id,
                    "amount_cents": bet.amount_cents,
                    "odds": str(bet.decimal_odds),
                    "status": bet.status,
                    "payout_cents": bet.payout_cents,
                }
                for bet in player_bets
            ],
            "seat_claim": _serialize_seat_claim(player_seat) if player_seat is not None else None,
            "recent_ledger": [
                {
                    "id": entry.pk,
                    "kind": entry.kind,
                    "amount_cents": entry.amount_cents,
                    "balance_after_cents": entry.balance_after_cents,
                    "description": entry.description,
                    "created_at": _timestamp(entry.created_at),
                }
                for entry in recent_ledger
            ],
        }
    return payload
