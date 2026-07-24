from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from btc_engine.core.clock import utc_now


@dataclass(slots=True)
class FeedState:
    name: str
    status: str = "starting"
    last_message_at: datetime | None = None
    last_error: str | None = None
    reconnects: int = 0
    sequence_gaps: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


class HealthRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._feeds: dict[str, FeedState] = {}

    async def update(self, name: str, **changes: object) -> None:
        async with self._lock:
            state = self._feeds.setdefault(name, FeedState(name=name))
            for key, value in changes.items():
                setattr(state, key, value)

    async def heartbeat(self, name: str, **metadata: object) -> None:
        async with self._lock:
            state = self._feeds.setdefault(name, FeedState(name=name))
            state.status = "healthy"
            state.last_message_at = utc_now()
            if metadata:
                state.metadata.update(metadata)

    async def error(self, name: str, error: BaseException) -> None:
        async with self._lock:
            state = self._feeds.setdefault(name, FeedState(name=name))
            state.status = "error"
            state.last_error = f"{type(error).__name__}: {error}"

    async def increment(self, name: str, field_name: str) -> None:
        async with self._lock:
            state = self._feeds.setdefault(name, FeedState(name=name))
            setattr(state, field_name, int(getattr(state, field_name)) + 1)

    async def snapshot(self) -> list[dict[str, object]]:
        async with self._lock:
            return [
                {
                    "name": s.name,
                    "status": s.status,
                    "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
                    "last_error": s.last_error,
                    "reconnects": s.reconnects,
                    "sequence_gaps": s.sequence_gaps,
                    "metadata": dict(s.metadata),
                }
                for s in self._feeds.values()
            ]
