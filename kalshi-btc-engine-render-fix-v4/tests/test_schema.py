from pathlib import Path

from btc_engine.storage.models import Base
from btc_engine.storage.schema import REQUIRED_TABLES


def test_required_schema_contains_core_tables() -> None:
    assert {
        "market_snapshots",
        "cfbenchmark_ticks",
        "kalshi_book_events",
        "kalshi_tickers",
        "kalshi_trades",
        "exchange_book_events",
        "exchange_trades",
        "feed_health_events",
        "db_batch_commits",
        "research_hypotheses",
    }.issubset(REQUIRED_TABLES)
    assert REQUIRED_TABLES == frozenset(Base.metadata.tables.keys())


def test_repair_migration_is_chained_after_initial() -> None:
    migration = Path("alembic/versions/0002_repair_missing_schema.py").read_text()
    assert 'revision = "0002"' in migration
    assert 'down_revision = "0001"' in migration
    assert "checkfirst=True" in migration
