from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db.models import Count, F, Q, QuerySet, Sum, Window
from django.db.models.functions import RowNumber

from apps.betting.models import Bet
from apps.racing.models import RaceEntry, Round

SETTLED_BET_STATUSES = (Bet.Status.WON, Bet.Status.LOST)
RECENT_RACE_HISTORY_LIMIT = 20
RECENT_RACER_FORM_LIMIT = 50
DNF_REASON_LABELS = {
    "fire_pit": "Fire pit",
    "stomped": "Run over / stomped",
    "knocked_out": "Knocked out",
    "finish_countdown": "Finish clock",
    "track_consumed": "Track consumed",
    "identity_stolen": "Identity stolen",
    "eliminated": "Eliminated",
}


@dataclass(frozen=True, slots=True)
class PlayerBettingRecord:
    player_id: int
    winning_bets: int = 0
    losing_bets: int = 0
    total_staked_cents: int = 0
    total_returned_cents: int = 0
    net_cents: int = 0

    @property
    def total_bets(self) -> int:
        return self.winning_bets + self.losing_bets


@dataclass(frozen=True, slots=True)
class RacerPerformanceRecord:
    racer_id: int
    starts: int = 0
    wins: int = 0
    losses: int = 0
    dnfs: int = 0
    win_rate: float = 0.0
    dnf_reason_counts: tuple[tuple[str, int], ...] = ()

    @property
    def finishes(self) -> int:
        return self.starts - self.dnfs

    def dnf_reason_count(self, reason: str) -> int:
        return dict(self.dnf_reason_counts).get(reason, 0)


@dataclass(frozen=True, slots=True)
class RacerRoundHistoryRow:
    round_number: int
    lane: int
    odds: str
    finish_place: int | None
    dnf_reason: str


def settled_round_count() -> int:
    return Round.objects.filter(settled_at__isnull=False).count()


def _player_betting_queryset(*, player_ids: list[int] | None = None) -> QuerySet[Bet]:
    queryset = Bet.objects.filter(status__in=SETTLED_BET_STATUSES)
    if player_ids is not None:
        queryset = queryset.filter(player_id__in=player_ids)
    return queryset


def player_betting_records(
    *, player_ids: list[int] | None = None
) -> dict[int, PlayerBettingRecord]:
    rows = (
        _player_betting_queryset(player_ids=player_ids)
        .values("player_id")
        .annotate(
            winning_bets=Count("id", filter=Q(status=Bet.Status.WON)),
            losing_bets=Count("id", filter=Q(status=Bet.Status.LOST)),
            total_staked_cents=Sum("amount_cents"),
            total_returned_cents=Sum("payout_cents"),
        )
    )
    return _player_betting_records_from_rows(rows)


def _player_betting_records_from_rows(
    rows: Iterable[dict[str, Any]],
) -> dict[int, PlayerBettingRecord]:
    records: dict[int, PlayerBettingRecord] = {}
    for row in rows:
        total_staked = int(row["total_staked_cents"] or 0)
        total_returned = int(row["total_returned_cents"] or 0)
        records[row["player_id"]] = PlayerBettingRecord(
            player_id=row["player_id"],
            winning_bets=int(row["winning_bets"]),
            losing_bets=int(row["losing_bets"]),
            total_staked_cents=total_staked,
            total_returned_cents=total_returned,
            net_cents=total_returned - total_staked,
        )
    return records


def top_player_betting_losses(*, limit: int = 8) -> dict[int, PlayerBettingRecord]:
    if limit <= 0:
        return {}
    rows = (
        _player_betting_queryset()
        .values("player_id")
        .annotate(
            winning_bets=Count("id", filter=Q(status=Bet.Status.WON)),
            losing_bets=Count("id", filter=Q(status=Bet.Status.LOST)),
            total_staked_cents=Sum("amount_cents"),
            total_returned_cents=Sum("payout_cents"),
        )
        .annotate(net_cents=F("total_returned_cents") - F("total_staked_cents"))
        .filter(net_cents__lt=0)
        .order_by("net_cents", "player_id")[:limit]
    )
    return _player_betting_records_from_rows(rows)


def _settled_race_entry_queryset(*, racer_ids: list[int] | None = None) -> QuerySet[RaceEntry]:
    queryset = RaceEntry.objects.filter(race__round__settled_at__isnull=False)
    if racer_ids is not None:
        queryset = queryset.filter(racer_id__in=racer_ids)
    return queryset


def racer_performance_records(
    *, racer_ids: list[int] | None = None
) -> dict[int, RacerPerformanceRecord]:
    rows = (
        _settled_race_entry_queryset(racer_ids=racer_ids)
        .values("racer_id")
        .annotate(
            starts=Count("id"),
            wins=Count("id", filter=Q(finish_place=1)),
            dnfs=Count("id", filter=Q(finish_place__isnull=True)),
        )
    )
    records: dict[int, RacerPerformanceRecord] = {}
    for row in rows:
        starts = int(row["starts"])
        wins = int(row["wins"])
        dnfs = int(row["dnfs"])
        losses = starts - wins
        win_rate = wins / starts if starts else 0.0
        records[row["racer_id"]] = RacerPerformanceRecord(
            racer_id=row["racer_id"],
            starts=starts,
            wins=wins,
            losses=losses,
            dnfs=dnfs,
            win_rate=win_rate,
        )
    return records


def racer_performance_record(*, racer_id: int) -> RacerPerformanceRecord:
    return racer_performance_records(racer_ids=[racer_id]).get(
        racer_id,
        RacerPerformanceRecord(racer_id),
    )


def _performance_record_from_outcomes(
    racer_id: int,
    outcomes: Iterable[tuple[int | None, str]],
) -> RacerPerformanceRecord:
    outcome_list = list(outcomes)
    starts = len(outcome_list)
    wins = sum(finish_place == 1 for finish_place, _reason in outcome_list)
    reasons = Counter(
        reason
        for finish_place, reason in outcome_list
        if finish_place is None and reason
    )
    dnfs = sum(finish_place is None for finish_place, _reason in outcome_list)
    return RacerPerformanceRecord(
        racer_id=racer_id,
        starts=starts,
        wins=wins,
        losses=starts - wins,
        dnfs=dnfs,
        win_rate=wins / starts if starts else 0.0,
        dnf_reason_counts=tuple(sorted(reasons.items())),
    )


def racer_recent_performance_records(
    *,
    racer_ids: list[int],
    limit: int = RECENT_RACER_FORM_LIMIT,
) -> dict[int, RacerPerformanceRecord]:
    if limit <= 0 or not racer_ids:
        return {}
    recent_entries = (
        _settled_race_entry_queryset(racer_ids=racer_ids)
        .annotate(
            recent_rank=Window(
                expression=RowNumber(),
                partition_by=[F("racer_id")],
                order_by=[
                    F("race__round__number").desc(),
                    F("pk").desc(),
                ],
            )
        )
        .filter(recent_rank__lte=limit)
        .values_list("racer_id", "finish_place", "dnf_reason")
    )
    outcomes_by_racer: defaultdict[int, list[tuple[int | None, str]]] = defaultdict(list)
    for racer_id, finish_place, dnf_reason in recent_entries:
        outcomes_by_racer[racer_id].append((finish_place, dnf_reason))
    return {
        racer_id: _performance_record_from_outcomes(racer_id, outcomes)
        for racer_id, outcomes in outcomes_by_racer.items()
    }


def racer_recent_performance_record(
    *,
    racer_id: int,
    limit: int = RECENT_RACER_FORM_LIMIT,
) -> RacerPerformanceRecord:
    return racer_recent_performance_records(racer_ids=[racer_id], limit=limit).get(
        racer_id,
        RacerPerformanceRecord(racer_id),
    )


def dnf_reason_label(reason: str) -> str:
    return DNF_REASON_LABELS.get(reason, "Eliminated")


def racer_recent_history(
    *, racer_id: int, limit: int = RECENT_RACE_HISTORY_LIMIT
) -> list[RacerRoundHistoryRow]:
    entries = (
        RaceEntry.objects.filter(
            racer_id=racer_id,
            race__round__settled_at__isnull=False,
        )
        .select_related("race__round")
        .order_by("-race__round__number")[:limit]
    )
    return [
        RacerRoundHistoryRow(
            round_number=entry.race.round.number,
            lane=entry.lane,
            odds=str(entry.odds),
            finish_place=entry.finish_place,
            dnf_reason=entry.dnf_reason,
        )
        for entry in entries
    ]


def serialize_player_betting_record(record: PlayerBettingRecord) -> dict[str, Any]:
    return {
        "winning_bets": record.winning_bets,
        "losing_bets": record.losing_bets,
        "total_bets": record.total_bets,
        "total_staked_cents": record.total_staked_cents,
        "total_returned_cents": record.total_returned_cents,
        "net_cents": record.net_cents,
    }


def serialize_racer_performance_record(record: RacerPerformanceRecord) -> dict[str, Any]:
    return {
        "starts": record.starts,
        "wins": record.wins,
        "losses": record.losses,
        "dnfs": record.dnfs,
        "win_rate": round(record.win_rate, 4),
    }


def serialize_racer_history_row(row: RacerRoundHistoryRow) -> dict[str, Any]:
    return {
        "round_number": row.round_number,
        "lane": row.lane,
        "odds": row.odds,
        "finish_place": row.finish_place,
        "dnf_reason": row.dnf_reason,
        "dnf_label": dnf_reason_label(row.dnf_reason),
    }
