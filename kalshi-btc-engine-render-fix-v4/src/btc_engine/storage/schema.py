from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from btc_engine.storage.models import Base

REQUIRED_TABLES = frozenset(Base.metadata.tables.keys())


async def ensure_schema(engine: AsyncEngine) -> None:
    """Create any missing Phase-1 tables without deleting existing data.

    Alembic remains the versioning authority. This check is an idempotent safety
    net for early deployments whose version table was stamped before the full
    schema existed.
    """
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                bind=sync_connection,
                checkfirst=True,
            )
        )


async def get_missing_tables(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        existing = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
    return sorted(REQUIRED_TABLES - existing)
