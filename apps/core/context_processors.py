from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def app_context(request: HttpRequest) -> dict[str, Any]:
    return {
        "game_player": getattr(request, "game_player", None),
    }
