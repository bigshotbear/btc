from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampColumns:
    db_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receive_wall_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    receive_monotonic_ns: Mapped[int] = mapped_column(BigInteger, nullable=False)
    db_enqueued_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_ticker: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    series_ticker: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    open_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    strike_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    floor_strike: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    rules_primary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_secondary: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_close_early: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class LifecycleEvent(Base, TimestampColumns):
    __tablename__ = "lifecycle_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_ticker: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_ticker: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class CFBenchmarkTick(Base, TimestampColumns):
    __tablename__ = "cfbenchmark_ticks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    index_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    trailing_60s_average: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    trailing_60s_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quarter_final_minute_average: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quarter_final_minute_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quarter_window_start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quarter_window_end_exclusive_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class KalshiBookEvent(Base, TimestampColumns):
    __tablename__ = "kalshi_book_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_ticker: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    book_side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    normalized_yes_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    use_yes_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class KalshiTicker(Base, TimestampColumns):
    __tablename__ = "kalshi_tickers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_ticker: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    yes_bid: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    yes_ask: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    yes_bid_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    yes_ask_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class KalshiTrade(Base, TimestampColumns):
    __tablename__ = "kalshi_trades"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    market_ticker: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    yes_price: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    no_price: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    taker_outcome_side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    taker_book_side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ExchangeBookEvent(Base, TimestampColumns):
    __tablename__ = "exchange_book_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ExchangeTrade(Base, TimestampColumns):
    __tablename__ = "exchange_trades"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trade_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    aggressor_side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    raw_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DBBatchCommit(Base):
    __tablename__ = "db_batch_commits"
    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    commit_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_ms: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    tables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FeedHealthEvent(Base):
    __tablename__ = "feed_health_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    feed: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ResearchHypothesis(Base):
    __tablename__ = "research_hypotheses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decision_criterion: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


Index("ix_cfbenchmark_index_source_ms", CFBenchmarkTick.index_id, CFBenchmarkTick.source_timestamp_ms)
Index("ix_exchange_book_exchange_symbol_receive", ExchangeBookEvent.exchange, ExchangeBookEvent.symbol, ExchangeBookEvent.receive_wall_time)
Index("ix_exchange_trade_exchange_symbol_receive", ExchangeTrade.exchange, ExchangeTrade.symbol, ExchangeTrade.receive_wall_time)
Index("ix_kalshi_book_ticker_receive", KalshiBookEvent.market_ticker, KalshiBookEvent.receive_wall_time)
