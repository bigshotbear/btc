from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase

from btc_engine.logging import get_logger
from btc_engine.storage.models import DBBatchCommit

logger = get_logger(__name__)


@dataclass(slots=True)
class WriteItem:
    model: type[DeclarativeBase]
    values: dict[str, Any]


class BatchDBWriter:
    def __init__(self, engine: AsyncEngine, batch_size: int = 500, flush_interval_ms: int = 250) -> None:
        self.engine = engine
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000
        self.queue: asyncio.Queue[WriteItem] = asyncio.Queue(maxsize=batch_size * 20)
        self._stopping = asyncio.Event()

    async def put(self, model: type[DeclarativeBase], values: dict[str, Any]) -> None:
        if hasattr(model, "db_enqueued_time"):
            values.setdefault("db_enqueued_time", datetime.now(UTC))
        await self.queue.put(WriteItem(model=model, values=values))

    async def run(self) -> None:
        while not self._stopping.is_set() or not self.queue.empty():
            batch: list[WriteItem] = []
            try:
                first = await asyncio.wait_for(self.queue.get(), timeout=self.flush_interval)
                batch.append(first)
            except TimeoutError:
                continue
            deadline = asyncio.get_running_loop().time() + self.flush_interval
            while len(batch) < self.batch_size:
                timeout = deadline - asyncio.get_running_loop().time()
                if timeout <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self.queue.get(), timeout=timeout))
                except TimeoutError:
                    break
            retry_delay = 0.5
            while True:
                try:
                    await self._flush(batch)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(30.0, retry_delay * 2)
            for _ in batch:
                self.queue.task_done()

    async def _flush(self, batch: list[WriteItem]) -> None:
        batch_id = str(uuid.uuid4())
        grouped: dict[type[DeclarativeBase], list[dict[str, Any]]] = defaultdict(list)
        for item in batch:
            if hasattr(item.model, "db_batch_id"):
                item.values.setdefault("db_batch_id", batch_id)
            grouped[item.model].append(item.values)
        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        try:
            async with self.engine.begin() as connection:
                for model, rows in grouped.items():
                    await connection.execute(insert(model), rows)
            completed_at = datetime.now(UTC)
            duration_ms = Decimal(str((time.perf_counter() - started_perf) * 1000))
        except Exception:
            logger.exception("db_batch_failed", row_count=len(batch), batch_id=batch_id)
            raise
        # The ledger is inserted after the data transaction has successfully committed.
        # A ledger outage must not cause already-committed market data to be replayed.
        try:
            async with self.engine.begin() as connection:
                await connection.execute(
                    insert(DBBatchCommit),
                    {
                        "batch_id": batch_id,
                        "row_count": len(batch),
                        "commit_started_at": started_at,
                        "commit_completed_at": completed_at,
                        "duration_ms": duration_ms,
                        "tables": {
                            model.__tablename__: len(rows) for model, rows in grouped.items()
                        },
                    },
                )
        except Exception:
            logger.exception("db_commit_ledger_failed", batch_id=batch_id)

    async def stop(self) -> None:
        self._stopping.set()
        await self.queue.join()
