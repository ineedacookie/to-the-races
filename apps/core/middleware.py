from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class StaticAssetCacheMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        asset_prefix = f"{settings.STATIC_URL.rstrip('/')}/assets/"
        cache_seconds = settings.STATIC_ASSET_CACHE_SECONDS
        if (
            request.method in {"GET", "HEAD"}
            and request.path.startswith(asset_prefix)
            and response.status_code in {200, 304}
            and cache_seconds > 0
        ):
            response.headers["Cache-Control"] = f"public, max-age={cache_seconds}"
        return response
