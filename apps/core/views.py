from __future__ import annotations

from io import BytesIO

import segno
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.betting.house_account import (
    HouseBreakdown,
    format_money,
    house_account_summary,
    house_round_history,
    recent_house_transactions,
)
from apps.players.middleware import ensure_request_device
from apps.racing.models import RaceEntry, Racer
from apps.racing.stats import (
    DNF_REASON_LABELS,
    RECENT_RACER_FORM_LIMIT,
    racer_performance_record,
    racer_recent_history,
    racer_recent_performance_record,
    serialize_racer_history_row,
    serialize_racer_performance_record,
)


def home(request: HttpRequest) -> HttpResponse:
    return redirect("betting-page")


@ensure_csrf_cookie
@cache_control(no_store=True)
def betting_page(request: HttpRequest) -> HttpResponse:
    ensure_request_device(request)
    return render(request, "betting/index.html")


@cache_control(no_store=True)
def display_page(request: HttpRequest) -> HttpResponse:
    bet_url = request.build_absolute_uri(reverse("betting-page"))
    return render(request, "display/index.html", {"bet_url": bet_url})


@cache_control(no_store=True)
def racer_detail(request: HttpRequest, slug: str) -> HttpResponse:
    racer = get_object_or_404(Racer, active=True, slug=slug)
    roster = list(Racer.objects.filter(active=True))
    stats = (
        ("Pace", round(racer.base_speed / 1.5 * 100), "Raw track speed"),
        ("Armor", round(racer.resilience * 100), "Shrugs off impacts"),
        ("Recovery", round(racer.recovery * 100), "Gets back up"),
        ("Aggro", round(racer.aggression * 100), "Starts trouble"),
        ("Chaos", round(racer.chaos * 100), "Ignores the plan"),
    )
    field_notes = [
        "Odds describe the opening market, not destiny. Every race is seeded chaos.",
        "After 50 settled starts, odds blend simulation with this racer's latest 50 results.",
        "Items bend probabilities; none can guarantee a finish or a DNF.",
    ]
    if racer.chaos >= 0.75:
        field_notes.append("Known to improvise routes that do not appear on any map.")
    if racer.aggression >= 0.75:
        field_notes.append("Personal-space policy: aggressively deprecated.")
    if racer.resilience >= 0.7:
        field_notes.append("Built to absorb incidents that require paperwork.")
    if racer.recovery >= 0.7:
        field_notes.append("Treats falling down as an unusually low starting stance.")

    record = racer_performance_record(racer_id=racer.pk)
    recent_form = racer_recent_performance_record(racer_id=racer.pk)
    recent_outcomes = [
        ("Win rate", recent_form.wins),
        ("Finish rate", recent_form.finishes),
        ("DNF rate", recent_form.dnfs),
        *[
            (label, recent_form.dnf_reason_count(reason))
            for reason, label in DNF_REASON_LABELS.items()
        ],
    ]
    known_dnf_count = sum(
        recent_form.dnf_reason_count(reason) for reason in DNF_REASON_LABELS
    )
    if known_dnf_count < recent_form.dnfs:
        recent_outcomes.append(("Other DNF", recent_form.dnfs - known_dnf_count))
    recent_form_payload = {
        "starts": recent_form.starts,
        "limit": RECENT_RACER_FORM_LIMIT,
        "outcomes": [
            {
                "label": label,
                "count": count,
                "percent": round(count / recent_form.starts * 100, 1)
                if recent_form.starts
                else 0.0,
            }
            for label, count in recent_outcomes
        ],
    }
    history = [serialize_racer_history_row(row) for row in racer_recent_history(racer_id=racer.pk)]
    record_payload = serialize_racer_performance_record(record)
    record_payload["win_rate_percent"] = round(record.win_rate * 100, 1)
    current_entry = (
        RaceEntry.objects.filter(racer=racer)
        .select_related("race__round")
        .order_by("-race__round__number")
        .first()
    )

    return render(
        request,
        "racers/detail.html",
        {
            "racer": racer,
            "roster": roster,
            "stats": stats,
            "field_notes": field_notes,
            "record": record_payload,
            "recent_form": recent_form_payload,
            "history": history,
            "current_odds": (
                current_entry.odds if current_entry is not None else racer.default_odds
            ),
            "current_odds_round": (
                current_entry.race.round.number if current_entry is not None else None
            ),
        },
    )


def _house_breakdown_context(breakdown: HouseBreakdown) -> dict[str, str | int]:
    return {
        "stakes_collected": format_money(breakdown.stakes_collected_cents),
        "payouts_paid": format_money(breakdown.payouts_paid_cents),
        "refunds_paid": format_money(breakdown.refunds_paid_cents),
        "betting_net": format_money(breakdown.betting_net_cents),
        "betting_net_cents": breakdown.betting_net_cents,
        "item_sales": format_money(breakdown.item_sales_cents),
        "seat_sales": format_money(breakdown.seat_sales_cents),
        "upgrade_sales": format_money(breakdown.upgrade_sales_cents),
        "commerce_revenue": format_money(breakdown.commerce_revenue_cents),
        "bailouts_paid": format_money(breakdown.bailouts_paid_cents),
        "operating_net": format_money(breakdown.operating_net_cents),
        "operating_net_cents": breakdown.operating_net_cents,
    }


@cache_control(no_store=True)
def house_account(request: HttpRequest) -> HttpResponse:
    summary = house_account_summary()
    history = [
        {
            "round_number": row.round_number,
            "settled_at": row.settled_at,
            "winner_name": row.winner_name,
            "house_won": row.house_won,
            **_house_breakdown_context(row.breakdown),
        }
        for row in house_round_history()
    ]
    transactions = [
        {
            "label": row.label,
            "player_nickname": row.player_nickname,
            "round_number": row.round_number,
            "description": row.description,
            "house_delta": format_money(row.house_delta_cents),
            "house_delta_cents": row.house_delta_cents,
            "created_at": row.created_at,
        }
        for row in recent_house_transactions()
    ]
    return render(
        request,
        "house/account.html",
        {
            "summary": {
                **_house_breakdown_context(summary.breakdown),
                "settled_rounds": summary.settled_rounds,
                "house_win_rounds": summary.house_win_rounds,
                "player_count": summary.player_count,
                "operating_transactions": summary.operating_transactions,
                "opening_grants": format_money(summary.opening_grants_cents),
                "admin_adjustments": format_money(summary.admin_adjustments_cents),
            },
            "history": history,
            "transactions": transactions,
        },
    )


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True})


@cache_control(public=True, max_age=60)
def betting_qr(request: HttpRequest) -> HttpResponse:
    bet_url = request.build_absolute_uri(reverse("betting-page"))
    qr_code = segno.make(bet_url, error="m")
    buffer = BytesIO()
    qr_code.save(buffer, kind="svg", scale=5, border=2, dark="#18212b", light="#fff8e7")
    return HttpResponse(buffer.getvalue(), content_type="image/svg+xml")
