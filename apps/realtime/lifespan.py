from __future__ import annotations

from typing import Any

from apps.racing.coordinator import coordinator


class GameLifespanApplication:
    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        while True:
            message = await receive()
            message_type = message["type"]
            if message_type == "lifespan.startup":
                await coordinator.start()
                await send({"type": "lifespan.startup.complete"})
            elif message_type == "lifespan.shutdown":
                await coordinator.stop()
                await send({"type": "lifespan.shutdown.complete"})
                return
