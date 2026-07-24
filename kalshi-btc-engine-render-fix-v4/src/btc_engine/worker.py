from __future__ import annotations

import asyncio
from datetime import UTC, datetime


from btc_engine.collectors.coinbase import CoinbaseCollector
from btc_engine.collectors.kalshi import KalshiCollector
from btc_engine.collectors.kraken import KrakenCollector
from btc_engine.config import get_settings
from btc_engine.core.health import HealthRegistry
from btc_engine.logging import configure_logging
from btc_engine.research.confluence_registry import INITIAL_HYPOTHESES
from btc_engine.storage.database import create_engine
from btc_engine.storage.models import FeedHealthEvent, ResearchHypothesis
from btc_engine.storage.raw_archive import RawArchive
from btc_engine.storage.schema import ensure_schema
from btc_engine.storage.writer import BatchDBWriter

from btc_engine.logging import get_logger

logger = get_logger(__name__)


async def persist_health(health: HealthRegistry, writer: BatchDBWriter) -> None:
    while True:
        snapshot = await health.snapshot()
        now = datetime.now(UTC)
        for feed in snapshot:
            await writer.put(
                FeedHealthEvent,
                {
                    "recorded_at": now,
                    "feed": feed["name"],
                    "status": feed["status"],
                    "event_type": "heartbeat",
                    "details": feed,
                },
            )
        await asyncio.sleep(5)


async def seed_hypotheses(writer: BatchDBWriter) -> None:
    # The unique key prevents accidental duplication; duplicate insert failures are
    # avoided by leaving seeding to the migration in future versions. For Phase 1,
    # write only when explicitly called in a clean database.
    for hypothesis in INITIAL_HYPOTHESES:
        await writer.put(
            ResearchHypothesis,
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "created_at": hypothesis.created_at,
                "feature_name": hypothesis.feature_name,
                "rationale": hypothesis.rationale,
                "decision_criterion": hypothesis.decision_criterion,
                "status": "proposed",
                "result": None,
            },
        )


async def async_main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    await ensure_schema(engine)
    writer = BatchDBWriter(engine, settings.db_batch_size, settings.db_flush_interval_ms)
    archive = RawArchive(settings.raw_data_dir, settings.raw_archive_enabled)
    health = HealthRegistry()

    tasks: list[asyncio.Task] = [
        asyncio.create_task(writer.run(), name="db-writer"),
        asyncio.create_task(archive.run(), name="raw-archive"),
        asyncio.create_task(persist_health(health, writer), name="health-persist"),
    ]
    if settings.kalshi_enable:
        tasks.append(
            asyncio.create_task(
                KalshiCollector(settings, writer, archive, health).run(), name="kalshi"
            )
        )
    if settings.coinbase_enable:
        tasks.append(
            asyncio.create_task(
                CoinbaseCollector(settings, writer, archive, health).run(), name="coinbase"
            )
        )
    if settings.kraken_enable:
        tasks.append(
            asyncio.create_task(
                KrakenCollector(settings, writer, archive, health).run(), name="kraken"
            )
        )

    logger.info("worker_started", tasks=[task.get_name() for task in tasks])
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks[2:]:
            task.cancel()
        await asyncio.gather(*tasks[2:], return_exceptions=True)
        await archive.stop()
        await writer.stop()
        for task in tasks[:2]:
            task.cancel()
        await asyncio.gather(*tasks[:2], return_exceptions=True)
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
