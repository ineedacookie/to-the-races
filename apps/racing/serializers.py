from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from apps.betting.bailout_services import serialize_track_medic
from apps.betting.models import Bet, LedgerEntry
from apps.players.models import Player
from apps.players.serialization import player_identity_fields
from apps.racing.models import (
    InventoryItem,
    ItemDefinition,
    PlayerUpgrade,
    RaceEntry,
    RoomSettings,
    Round,
    RoundItemUse,
    RoundSeatMarket,
    SeatOwnership,
    SpectatorSeatDefinition,
    UpgradeDefinition,
)
from apps.racing.replay_montage import replay_manifest
from apps.racing.round_guards import active_show_round, latest_round
from apps.racing.stats import (
    PlayerBettingRecord,
    RacerPerformanceRecord,
    player_betting_records,
    racer_recent_performance_records,
    serialize_player_betting_record,
    serialize_racer_performance_record,
    top_player_betting_losses,
)
from apps.racing.upgrade_services import (
    effective_inventory_capacity,
    next_inventory_upgrade,
)
from apps.realtime.presence import connected_spectators


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


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
            "payout_bonus_bps": seat.payout_bonus_bps,
        }
        for seat in SpectatorSeatDefinition.objects.filter(active=True)
    ]


def _serialize_upgrade_definition(upgrade: UpgradeDefinition) -> dict[str, Any]:
    prerequisite = upgrade.prerequisite
    return {
        "slug": upgrade.slug,
        "name": upgrade.name,
        "description": upgrade.description,
        "kind": upgrade.kind,
        "inventory_capacity": upgrade.inventory_capacity,
        "price_cents": upgrade.price_cents,
        "prerequisite_slug": prerequisite.slug if prerequisite is not None else None,
    }


def _upgrade_catalog(
    upgrades: list[UpgradeDefinition] | None = None,
) -> list[dict[str, Any]]:
    if upgrades is None:
        upgrades = list(
            UpgradeDefinition.objects.filter(active=True)
            .select_related("prerequisite")
            .order_by("sort_order", "name")
        )
    return [_serialize_upgrade_definition(upgrade) for upgrade in upgrades]


def _serialize_owned_upgrade(player_upgrade: PlayerUpgrade) -> dict[str, Any]:
    return {
        "slug": player_upgrade.upgrade.slug,
        "name": player_upgrade.upgrade.name,
        "kind": player_upgrade.upgrade.kind,
        "inventory_capacity": player_upgrade.upgrade.inventory_capacity,
        "price_paid_cents": player_upgrade.price_paid_cents,
        "purchased_at": _timestamp(player_upgrade.purchased_at),
    }


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
        "target_racer_id": (use.target_entry.racer_id if use.target_entry is not None else None),
        "target_racer_name": (
            use.target_entry.racer.name if use.target_entry is not None else None
        ),
        "track_lane": use.track_lane,
        "track_position": use.track_position,
        "activation_tick": use.activation_tick,
        "price_paid_cents": use.price_paid_cents,
        "created_at": _timestamp(use.created_at),
    }


def _serialize_inventory_item(inventory_item: InventoryItem) -> dict[str, Any]:
    return {
        "id": inventory_item.pk,
        "item_slug": inventory_item.item.slug,
        "item_name": inventory_item.item.name,
        "description": inventory_item.item.description,
        "item_icon": inventory_item.item.icon,
        "item_color": inventory_item.item.color,
        "kind": inventory_item.item.kind,
        "target": inventory_item.item.target,
        "price_paid_cents": inventory_item.price_paid_cents,
        "purchased_at": _timestamp(inventory_item.purchased_at),
    }


def _serialize_seat_ownership(
    ownership: SeatOwnership,
    *,
    market: RoundSeatMarket | None,
    online_player_ids: set[int],
) -> dict[str, Any]:
    current_price_cents = (
        market.current_price_cents if market is not None else ownership.seat.price_cents
    )
    return {
        "id": ownership.pk,
        "player_id": ownership.player_id,
        "seat_slug": ownership.seat.slug,
        "seat_name": ownership.seat.name,
        "seat_description": ownership.seat.description,
        "sprite_key": ownership.seat.sprite_key,
        "seat_color": ownership.seat.color,
        "payout_bonus_bps": ownership.seat.payout_bonus_bps,
        "current_price_cents": current_price_cents,
        "takeover_count": market.takeover_count if market is not None else 0,
        "nickname": ownership.player.nickname,
        "is_online": ownership.player_id in online_player_ids,
        "acquired_at": _timestamp(ownership.acquired_at),
    }


def _serialize_seat_market(market: RoundSeatMarket) -> dict[str, Any]:
    return {
        "seat_slug": market.seat.slug,
        "current_price_cents": market.current_price_cents,
        "takeover_count": market.takeover_count,
    }


def _player_board_rows(
    players: list[Player],
    betting_records: dict[int, PlayerBettingRecord],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, player in enumerate(players, start=1):
        record = betting_records.get(
            player.pk,
            PlayerBettingRecord(player.pk),
        )
        rows.append(
            {
                "rank": index,
                "player_id": player.pk,
                "nickname": player.nickname,
                "balance_cents": player.balance_cents,
                "total_bets": record.total_bets,
                "wins": record.winning_bets,
                "betting_record": serialize_player_betting_record(record),
            }
        )
    return rows


def _format_oops_ledger(
    records_by_player: dict[int, PlayerBettingRecord],
) -> list[dict[str, Any]]:
    records = list(records_by_player.values())
    if not records:
        return []

    players = {
        player.pk: player
        for player in Player.objects.filter(pk__in=[record.player_id for record in records])
    }
    ordered_players = [players[record.player_id] for record in records]
    return _player_board_rows(ordered_players, records_by_player)


def _serialize_player_state(
    *,
    player: Player,
    room: RoomSettings,
    current_round: Round | None,
    track_medic_round: Round | None,
    betting_record: PlayerBettingRecord,
    upgrade_catalog: list[UpgradeDefinition],
    item_uses: list[RoundItemUse],
    seat_ownerships: list[SeatOwnership],
    market_by_seat_id: dict[int, RoundSeatMarket],
    online_player_ids: set[int],
) -> dict[str, Any]:
    player_inventory = list(
        InventoryItem.objects.filter(
            player=player,
            used_at__isnull=True,
            discarded_at__isnull=True,
        )
        .select_related("item")
        .order_by("purchased_at", "pk")
    )
    owned_upgrades = list(
        PlayerUpgrade.objects.filter(player=player)
        .select_related("upgrade")
        .order_by("purchased_at", "pk")
    )
    owned_upgrade_slugs = {owned.upgrade.slug for owned in owned_upgrades}
    inventory_capacity = effective_inventory_capacity(
        player=player,
        room=room,
        owned_capacities=[
            owned.upgrade.inventory_capacity
            for owned in owned_upgrades
            if owned.upgrade.kind == UpgradeDefinition.Kind.INVENTORY_CAPACITY
        ],
    )
    next_upgrade = next_inventory_upgrade(
        player=player,
        catalog=upgrade_catalog,
        owned_slugs=owned_upgrade_slugs,
    )
    player_bets = (
        list(
            Bet.objects.filter(player=player, round=current_round).select_related(
                "race_entry__racer"
            )
        )
        if current_round is not None
        else []
    )
    round_staked_cents = sum(bet.amount_cents for bet in player_bets)
    player_item_uses = [use for use in item_uses if use.player_id == player.pk]
    player_seat = next(
        (ownership for ownership in seat_ownerships if ownership.player_id == player.pk),
        None,
    )
    player_market = market_by_seat_id.get(player_seat.seat_id) if player_seat is not None else None
    recent_ledger = list(
        LedgerEntry.objects.filter(player=player).order_by("-created_at", "-pk")[:8]
    )
    return {
        **player_identity_fields(player, include_avatar_recipe=True),
        "round_staked_cents": round_staked_cents,
        "round_stake_remaining_cents": max(
            room.max_round_stake_cents - round_staked_cents,
            0,
        ),
        "round_item_spent_cents": sum(use.price_paid_cents for use in player_item_uses),
        "effective_inventory_capacity": inventory_capacity,
        "next_inventory_upgrade": (
            _serialize_upgrade_definition(next_upgrade) if next_upgrade is not None else None
        ),
        "owned_upgrades": [
            _serialize_owned_upgrade(player_upgrade) for player_upgrade in owned_upgrades
        ],
        "inventory": [
            _serialize_inventory_item(inventory_item) for inventory_item in player_inventory
        ],
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
        "seat_claim": (
            _serialize_seat_ownership(
                player_seat,
                market=player_market,
                online_player_ids=online_player_ids,
            )
            if player_seat is not None
            else None
        ),
        "betting_record": serialize_player_betting_record(betting_record),
        "track_medic": serialize_track_medic(
            player=player,
            current_round=track_medic_round,
        ),
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


def _serialize_round_payload(
    *,
    current_round: Round,
    include_timeline: bool,
    seat_ownerships: list[SeatOwnership],
    online_player_ids: set[int],
) -> tuple[dict[str, Any], list[RoundItemUse], dict[int, RoundSeatMarket]]:
    entries = list(
        RaceEntry.objects.filter(race=current_round.race)
        .select_related("racer")
        .order_by("lane")
    )
    racer_records = racer_recent_performance_records(
        racer_ids=[entry.racer_id for entry in entries],
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
    seat_markets = list(
        RoundSeatMarket.objects.filter(round=current_round)
        .select_related("seat")
        .order_by("seat__sort_order", "seat__name", "pk")
    )
    market_by_seat_id = {market.seat_id: market for market in seat_markets}
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
                "record": serialize_racer_performance_record(
                    racer_records.get(
                        entry.racer_id,
                        RacerPerformanceRecord(entry.racer_id),
                    )
                ),
            }
            for entry in entries
        ],
        "item_uses": [_serialize_item_use(use) for use in item_uses],
        "seats": [
            _serialize_seat_ownership(
                ownership,
                market=market_by_seat_id.get(ownership.seat_id),
                online_player_ids=online_player_ids,
            )
            for ownership in seat_ownerships
        ],
        "seat_markets": [_serialize_seat_market(market) for market in seat_markets],
        "result": race_result if results_visible else {},
    }
    if results_visible:
        round_payload["replay"] = replay_manifest(current_round.race.replay_montage or {})
        if include_timeline:
            round_payload["display_replay"] = current_round.race.replay_montage or {}
    if include_timeline and current_round.race.timeline:
        race_inputs = current_round.race.inputs or {}
        round_payload["race"] = {
            "seed": current_round.race.seed,
            "generated_at": _timestamp(current_round.race.generated_at),
            "tick_rate": current_round.race.tick_rate,
            "duration_ticks": current_round.race.duration_ticks,
            "timeline": current_round.race.timeline,
            "events": current_round.race.events,
            "effects": race_inputs.get("effects", []),
            "successful_effect_ids": race_inputs.get("successful_effect_ids", []),
            "failed_effect_ids": race_inputs.get("failed_effect_ids", []),
        }
    return round_payload, item_uses, market_by_seat_id


def build_live_state(
    *,
    player_id: int | None = None,
    include_timeline: bool = False,
) -> dict[str, Any]:
    room = RoomSettings.load()
    current_time = timezone.now()
    current_round = latest_round(select_race=True)
    show_round = active_show_round(select_race=True, now=current_time)
    if (
        current_round is not None
        and show_round is not None
        and show_round.pk == current_round.pk
    ):
        show_round = None
    player = Player.objects.filter(pk=player_id).first() if player_id is not None else None
    leaderboard_players = list(Player.objects.order_by("-balance_cents", "nickname")[:8])
    record_player_ids = {leader.pk for leader in leaderboard_players}
    if player is not None:
        record_player_ids.add(player.pk)
    betting_records = player_betting_records(player_ids=sorted(record_player_ids))
    loss_records = top_player_betting_losses()
    upgrade_catalog = list(
        UpgradeDefinition.objects.filter(active=True)
        .select_related("prerequisite")
        .order_by("sort_order", "name")
    )
    online_player_ids = {spectator.player_id for spectator in connected_spectators()}
    seat_ownerships = list(
        SeatOwnership.objects.select_related("player", "seat").order_by(
            "seat__sort_order",
            "seat__name",
            "pk",
        )
    )
    payload: dict[str, Any] = {
        "protocol_version": 17,
        "server_time": current_time.isoformat(),
        "room": {
            "name": room.name,
            "is_paused": room.is_paused,
            "broadcast_enabled": room.broadcast_enabled,
            "betting_seconds": room.betting_seconds,
            "max_round_stake_cents": room.max_round_stake_cents,
            "max_inventory_items": room.max_inventory_items,
            "max_round_item_spend_cents": room.max_round_item_spend_cents,
            "max_round_item_uses": room.max_round_item_uses,
            "item_catalog": _item_catalog(),
            "seat_catalog": _seat_catalog(),
            "upgrade_catalog": _upgrade_catalog(upgrade_catalog),
        },
        "leaderboard": _player_board_rows(leaderboard_players, betting_records),
        "debt_board": _format_oops_ledger(loss_records),
        "round": None,
        "show_round": None,
        "player": None,
    }
    if current_round is None:
        if player is not None:
            payload["player"] = _serialize_player_state(
                player=player,
                room=room,
                current_round=None,
                track_medic_round=None,
                betting_record=betting_records.get(
                    player.pk,
                    PlayerBettingRecord(player.pk),
                ),
                upgrade_catalog=upgrade_catalog,
                item_uses=[],
                seat_ownerships=seat_ownerships,
                market_by_seat_id={},
                online_player_ids=online_player_ids,
            )
        return payload

    round_payload, item_uses, market_by_seat_id = _serialize_round_payload(
        current_round=current_round,
        include_timeline=include_timeline,
        seat_ownerships=seat_ownerships,
        online_player_ids=online_player_ids,
    )
    payload["round"] = round_payload
    if show_round is not None:
        show_payload, _show_item_uses, _show_markets = _serialize_round_payload(
            current_round=show_round,
            include_timeline=include_timeline,
            seat_ownerships=seat_ownerships,
            online_player_ids=online_player_ids,
        )
        payload["show_round"] = show_payload

    if player is not None:
        payload["player"] = _serialize_player_state(
            player=player,
            room=room,
            current_round=current_round,
            track_medic_round=show_round or current_round,
            betting_record=betting_records.get(
                player.pk,
                PlayerBettingRecord(player.pk),
            ),
            upgrade_catalog=upgrade_catalog,
            item_uses=item_uses,
            seat_ownerships=seat_ownerships,
            market_by_seat_id=market_by_seat_id,
            online_player_ids=online_player_ids,
        )
    return payload
