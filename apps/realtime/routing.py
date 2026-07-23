from __future__ import annotations

from django.urls import path

from apps.realtime.consumers import LiveGameConsumer

websocket_urlpatterns = [
    # Django's path() stub only models HTTP callables; Channels accepts ASGI callables.
    path("ws/live/", LiveGameConsumer.as_asgi()),  # type: ignore[arg-type]
]
