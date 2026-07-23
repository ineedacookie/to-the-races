from __future__ import annotations

from io import BytesIO

import segno
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.players.middleware import ensure_request_device


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


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True})


@cache_control(public=True, max_age=60)
def betting_qr(request: HttpRequest) -> HttpResponse:
    bet_url = request.build_absolute_uri(reverse("betting-page"))
    qr_code = segno.make(bet_url, error="m")
    buffer = BytesIO()
    qr_code.save(buffer, kind="svg", scale=5, border=2, dark="#18212b", light="#fff8e7")
    return HttpResponse(buffer.getvalue(), content_type="image/svg+xml")
