from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from django.db.models import Count, Sum

from apps.betting.models import Bet
from apps.players.models import Player
from apps.players.serialization import player_identity_fields
from apps.racing.models import Round

SpotlightFocus = Literal["gain", "loss", "both", "none"]


@dataclass(frozen=True, slots=True)
class BettingSpotlightPlayer:
    player_id: int
    nickname: str
    avatar_url: str
    bet_count: int
    staked_cents: int
    returned_cents: int
    net_cents: int


@dataclass(frozen=True, slots=True)
class RoundBettingSpotlight:
    bet_count: int
    player_count: int
    highest_gain: BettingSpotlightPlayer | None
    highest_loss: BettingSpotlightPlayer | None
    host_focus: SpotlightFocus


def _stable_choice(seed: str, options: tuple[SpotlightFocus, ...]) -> SpotlightFocus:
    digest = hashlib.sha256(seed.encode()).digest()
    return options[int.from_bytes(digest[:4], "big") % len(options)]


def _spotlight_player(
    row: dict[str, Any],
    players: dict[int, Player],
) -> BettingSpotlightPlayer:
    player_id = int(row["player_id"])
    player = players[player_id]
    identity = player_identity_fields(player)
    staked_cents = int(row["staked_cents"] or 0)
    returned_cents = int(row["returned_cents"] or 0)
    return BettingSpotlightPlayer(
        player_id=player_id,
        nickname=player.nickname,
        avatar_url=str(identity["avatar_url"]),
        bet_count=int(row["bet_count"]),
        staked_cents=staked_cents,
        returned_cents=returned_cents,
        net_cents=returned_cents - staked_cents,
    )


def round_betting_spotlight(
    current_round: Round,
    *,
    seed: str,
) -> RoundBettingSpotlight | None:
    rows = list(
        Bet.objects.filter(
            round=current_round,
            status__in=(Bet.Status.WON, Bet.Status.LOST),
        )
        .values("player_id")
        .annotate(
            bet_count=Count("id"),
            staked_cents=Sum("amount_cents"),
            returned_cents=Sum("payout_cents"),
        )
        .order_by("player_id")
    )
    if not rows:
        return None
    players = {
        player.pk: player
        for player in Player.objects.filter(
            pk__in=[int(row["player_id"]) for row in rows]
        )
    }
    summaries = [_spotlight_player(row, players) for row in rows]
    gains = [summary for summary in summaries if summary.net_cents > 0]
    losses = [summary for summary in summaries if summary.net_cents < 0]
    highest_gain = (
        max(gains, key=lambda summary: (summary.net_cents, -summary.player_id))
        if gains
        else None
    )
    highest_loss = (
        min(losses, key=lambda summary: (summary.net_cents, summary.player_id))
        if losses
        else None
    )
    if highest_gain is not None and highest_loss is not None:
        focus_options: tuple[SpotlightFocus, ...] = (
            "both",
            "both",
            "gain",
            "loss",
            "none",
        )
    elif highest_gain is not None:
        focus_options = ("gain", "gain", "none")
    elif highest_loss is not None:
        focus_options = ("loss", "loss", "none")
    else:
        focus_options = ("none",)
    return RoundBettingSpotlight(
        bet_count=sum(summary.bet_count for summary in summaries),
        player_count=len(summaries),
        highest_gain=highest_gain,
        highest_loss=highest_loss,
        host_focus=_stable_choice(f"{seed}:betting-spotlight", focus_options),
    )


def _serialize_player(player: BettingSpotlightPlayer | None) -> dict[str, Any] | None:
    if player is None:
        return None
    return {
        "player_id": player.player_id,
        "nickname": player.nickname,
        "avatar_url": player.avatar_url,
        "bet_count": player.bet_count,
        "staked_cents": player.staked_cents,
        "returned_cents": player.returned_cents,
        "net_cents": player.net_cents,
    }


def serialize_round_betting_spotlight(
    spotlight: RoundBettingSpotlight,
) -> dict[str, Any]:
    return {
        "bet_count": spotlight.bet_count,
        "player_count": spotlight.player_count,
        "highest_gain": _serialize_player(spotlight.highest_gain),
        "highest_loss": _serialize_player(spotlight.highest_loss),
        "host_focus": spotlight.host_focus,
    }
