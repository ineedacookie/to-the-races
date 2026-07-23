from __future__ import annotations

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_application = get_asgi_application()

# Django must populate its app registry before these modules import consumers and models.
from apps.realtime.lifespan import GameLifespanApplication  # noqa: E402
from apps.realtime.middleware import DeviceWebSocketMiddleware  # noqa: E402
from apps.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": DeviceWebSocketMiddleware(
            URLRouter(websocket_urlpatterns)  # type: ignore[arg-type]
        ),
        "lifespan": GameLifespanApplication(),
    }
)
