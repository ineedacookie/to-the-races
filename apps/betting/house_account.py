from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from django.db.models import QuerySet, Sum

from apps.betting.models import LedgerEntry
from apps.betting.money import format_money as format_money
from apps.players.models import Player
from apps.racing.models import RaceEntry, Round

HOUSE_HISTORY_LIMIT = 50
HOUSE_TRANSACTION_LIMIT = 30
OPERATING_KINDS = (
    LedgerEntry.Kind.STAKE,
    LedgerEntry.Kind.PAYOUT,
    LedgerEntry.Kind.REFUND,
    LedgerEntry.Kind.ITEM,
    LedgerEntry.Kind.SEAT,
    LedgerEntry.Kind.BAILOUT,
    LedgerEntry.Kind.UPGRADE,
)
TRANSACTION_KIND_LABELS: dict[str, str] = {
    LedgerEntry.Kind.STAKE: "Stake collected",
    LedgerEntry.Kind.PAYOUT: "Winnings paid",
    LedgerEntry.Kind.REFUND: "Refund paid",
    LedgerEntry.Kind.ADJUSTMENT: "Admin adjustment",
    LedgerEntry.Kind.ITEM: "Item sale",
    LedgerEntry.Kind.SEAT: "Seat sale",
    LedgerEntry.Kind.BAILOUT: "Track Medic payment",
    LedgerEntry.Kind.UPGRADE: "Upgrade sale",
}


@dataclass(frozen=True, slots=True)
class HouseBreakdown:
    stakes_collected_cents: int = 0
    payouts_paid_cents: int = 0
    refunds_paid_cents: int = 0
    item_sales_cents: int = 0
    seat_sales_cents: int = 0
    upgrade_sales_cents: int = 0
    bailouts_paid_cents: int = 0

    @property
    def betting_net_cents(self) -> int:
        return self.stakes_collected_cents - self.payouts_paid_cents - self.refunds_paid_cents

    @property
    def commerce_revenue_cents(self) -> int:
        return self.item_sales_cents + self.seat_sales_cents + self.upgrade_sales_cents

    @property
    def operating_net_cents(self) -> int:
        return self.betting_net_cents + self.commerce_revenue_cents - self.bailouts_paid_cents


@dataclass(frozen=True, slots=True)
class HouseAccountSummary:
    breakdown: HouseBreakdown
    settled_rounds: int
    house_win_rounds: int
    player_count: int
    operating_transactions: int
    opening_grants_cents: int
    admin_adjustments_cents: int


@dataclass(frozen=True, slots=True)
class HouseRoundHistoryRow:
    round_number: int
    settled_at: datetime
    winner_name: str | None
    house_won: bool
    breakdown: HouseBreakdown


@dataclass(frozen=True, slots=True)
class HouseTransactionRow:
    kind: str
    label: str
    player_nickname: str
    round_number: int | None
    description: str
    house_delta_cents: int
    created_at: datetime


def _raw_kind_totals(queryset: QuerySet[LedgerEntry]) -> dict[str, int]:
    return {
        row["kind"]: int(row["total_cents"] or 0)
        for row in queryset.values("kind").annotate(total_cents=Sum("amount_cents"))
    }


def _breakdown_from_player_totals(totals: dict[str, int]) -> HouseBreakdown:
    return HouseBreakdown(
        stakes_collected_cents=-totals.get(LedgerEntry.Kind.STAKE, 0),
        payouts_paid_cents=totals.get(LedgerEntry.Kind.PAYOUT, 0),
        refunds_paid_cents=totals.get(LedgerEntry.Kind.REFUND, 0),
        item_sales_cents=-totals.get(LedgerEntry.Kind.ITEM, 0),
        seat_sales_cents=-totals.get(LedgerEntry.Kind.SEAT, 0),
        upgrade_sales_cents=-totals.get(LedgerEntry.Kind.UPGRADE, 0),
        bailouts_paid_cents=totals.get(LedgerEntry.Kind.BAILOUT, 0),
    )


def house_account_summary() -> HouseAccountSummary:
    ledger = LedgerEntry.objects.all()
    operating_ledger = ledger.filter(kind__in=OPERATING_KINDS)
    breakdown = _breakdown_from_player_totals(_raw_kind_totals(operating_ledger))
    settled_rounds = Round.objects.filter(settled_at__isnull=False)
    opening_total = (
        ledger.filter(kind=LedgerEntry.Kind.OPENING).aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )
    adjustment_total = (
        ledger.filter(kind=LedgerEntry.Kind.ADJUSTMENT).aggregate(total=Sum("amount_cents"))[
            "total"
        ]
        or 0
    )
    return HouseAccountSummary(
        breakdown=breakdown,
        settled_rounds=settled_rounds.count(),
        house_win_rounds=settled_rounds.exclude(race__entries__finish_place=1).count(),
        player_count=Player.objects.count(),
        operating_transactions=operating_ledger.count(),
        opening_grants_cents=int(opening_total),
        admin_adjustments_cents=-int(adjustment_total),
    )


def house_round_history(
    *,
    limit: int = HOUSE_HISTORY_LIMIT,
) -> list[HouseRoundHistoryRow]:
    if limit <= 0:
        return []
    rounds = list(
        Round.objects.filter(settled_at__isnull=False)
        .select_related("race")
        .order_by("-number")[:limit]
    )
    if not rounds:
        return []

    round_ids = [current_round.pk for current_round in rounds]
    raw_totals_by_round: defaultdict[int, dict[str, int]] = defaultdict(dict)
    for row in (
        LedgerEntry.objects.filter(round_id__in=round_ids, kind__in=OPERATING_KINDS)
        .values("round_id", "kind")
        .annotate(total_cents=Sum("amount_cents"))
    ):
        raw_totals_by_round[row["round_id"]][row["kind"]] = int(row["total_cents"] or 0)

    winners_by_round = {
        entry.race.round_id: entry.racer.name
        for entry in RaceEntry.objects.filter(
            race__round_id__in=round_ids,
            finish_place=1,
        ).select_related("racer", "race")
    }
    return [
        HouseRoundHistoryRow(
            round_number=current_round.number,
            settled_at=current_round.settled_at,
            winner_name=winners_by_round.get(current_round.pk),
            house_won=current_round.pk not in winners_by_round,
            breakdown=_breakdown_from_player_totals(raw_totals_by_round.get(current_round.pk, {})),
        )
        for current_round in rounds
        if current_round.settled_at is not None
    ]


def recent_house_transactions(
    *,
    limit: int = HOUSE_TRANSACTION_LIMIT,
) -> list[HouseTransactionRow]:
    if limit <= 0:
        return []
    entries = (
        LedgerEntry.objects.exclude(kind=LedgerEntry.Kind.OPENING)
        .select_related("player", "round")
        .order_by("-created_at", "-pk")[:limit]
    )
    return [
        HouseTransactionRow(
            kind=entry.kind,
            label=TRANSACTION_KIND_LABELS.get(entry.kind, entry.get_kind_display()),
            player_nickname=entry.player.nickname,
            round_number=entry.round.number if entry.round is not None else None,
            description=entry.description,
            house_delta_cents=-entry.amount_cents,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
