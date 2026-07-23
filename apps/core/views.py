from __future__ import annotations

from io import BytesIO

import segno
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.players.middleware import ensure_request_device
from apps.racing.models import Racer


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

    return render(
        request,
        "racers/detail.html",
        {
            "racer": racer,
            "roster": roster,
            "stats": stats,
            "field_notes": field_notes,
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
