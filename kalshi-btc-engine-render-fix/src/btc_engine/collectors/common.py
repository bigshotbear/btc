from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable


from btc_engine.core.health import HealthRegistry

from btc_engine.logging import get_logger

logger = get_logger(__name__)


async def run_reconnecting(
    name: str,
    connect_once: Callable[[], Awaitable[None]],
    health: HealthRegistry,
    *,
    minimum_delay: float = 0.5,
    maximum_delay: float = 30.0,
) -> None:
    delay = minimum_delay
    while True:
        try:
            await health.update(name, status="connecting")
            await connect_once()
            delay = minimum_delay
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await health.error(name, exc)
            await health.increment(name, "reconnects")
            logger.exception("collector_disconnected", feed=name, retry_seconds=delay)
            await asyncio.sleep(delay + random.random() * min(delay, 1.0))
            delay = min(maximum_delay, delay * 2)
