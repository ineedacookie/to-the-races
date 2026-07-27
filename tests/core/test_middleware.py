from __future__ import annotations

from apps.core.middleware import StaticAssetCacheMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import override_settings


def response_for(path: str, *, status: int = 200) -> HttpResponse:
    request = HttpRequest()
    request.method = "GET"
    request.path = path
    middleware = StaticAssetCacheMiddleware(
        lambda _request: HttpResponse(status=status),
    )
    return middleware(request)


@override_settings(STATIC_ASSET_CACHE_SECONDS=3600)
def test_static_artwork_receives_a_freshness_lifetime() -> None:
    response = response_for("/static/assets/racers/portraits/skeleton.png")

    assert response.headers["Cache-Control"] == "public, max-age=3600"


@override_settings(STATIC_ASSET_CACHE_SECONDS=3600)
def test_dynamic_bundles_and_api_responses_are_not_cached_by_asset_policy() -> None:
    bundle_response = response_for("/static/dist/betting.js")
    api_response = response_for("/api/state/")

    assert "Cache-Control" not in bundle_response.headers
    assert "Cache-Control" not in api_response.headers


@override_settings(STATIC_ASSET_CACHE_SECONDS=0)
def test_asset_cache_can_be_disabled_for_development() -> None:
    response = response_for("/static/assets/items/potions/green.png")

    assert "Cache-Control" not in response.headers
