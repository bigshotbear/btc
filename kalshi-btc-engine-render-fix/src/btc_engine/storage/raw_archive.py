from __future__ import annotations

import asyncio
import gzip
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from btc_engine.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ArchiveItem:
    source: str
    received_at: datetime
    payload: dict[str, Any]


class RawArchive:
    """Batched native-rate JSONL archive.

    Files are hourly gzip streams. Appending creates concatenated gzip members,
    which standard gzip readers transparently decode.
    """

    def __init__(self, root: Path, enabled: bool = True, batch_size: int = 1000) -> None:
        self.root = root
        self.enabled = enabled
        self.batch_size = batch_size
        self.queue: asyncio.Queue[ArchiveItem] = asyncio.Queue(maxsize=batch_size * 20)
        self._stopping = asyncio.Event()

    async def put(self, source: str, payload: dict[str, Any], received_at: datetime) -> None:
        if self.enabled:
            await self.queue.put(ArchiveItem(source=source, payload=payload, received_at=received_at))

    async def run(self) -> None:
        if not self.enabled:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        while not self._stopping.is_set() or not self.queue.empty():
            items: list[ArchiveItem] = []
            try:
                items.append(await asyncio.wait_for(self.queue.get(), timeout=0.5))
            except TimeoutError:
                continue
            while len(items) < self.batch_size:
                try:
                    items.append(self.queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            await asyncio.to_thread(self._write_batch, items)
            for _ in items:
                self.queue.task_done()

    def _write_batch(self, items: list[ArchiveItem]) -> None:
        groups: dict[Path, list[bytes]] = {}
        for item in items:
            ts = item.received_at.astimezone(UTC)
            path = self.root / item.source / ts.strftime("%Y/%m/%d/%H.jsonl.gz")
            envelope = {
                "collector_receive_time": ts.isoformat(),
                "source": item.source,
                "payload": item.payload,
            }
            groups.setdefault(path, []).append(orjson.dumps(envelope) + b"\n")
        for path, lines in groups.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "ab", compresslevel=5) as handle:
                handle.writelines(lines)

    async def stop(self) -> None:
        self._stopping.set()
        if self.enabled:
            await self.queue.join()
