from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import orjson
import websockets
from dateutil.parser import isoparse

from btc_engine.auth.kalshi import KalshiSigner
from btc_engine.config import Settings
from btc_engine.core.clock import ReceiveStamp
from btc_engine.core.health import HealthRegistry
from btc_engine.core.sequence import SequenceGap, SequenceTracker
from btc_engine.storage.models import (
    CFBenchmarkTick,
    KalshiBookEvent,
    KalshiTicker,
    KalshiTrade,
    LifecycleEvent,
    MarketSnapshot,
)
from btc_engine.storage.raw_archive import RawArchive
from btc_engine.storage.writer import BatchDBWriter

from btc_engine.logging import get_logger

logger = get_logger(__name__)
WS_PATH = "/trade-api/ws/v2"


def _dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    return isoparse(str(value)).astimezone(UTC)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


class KalshiCollector:
    name = "kalshi"

    def __init__(
        self,
        settings: Settings,
        writer: BatchDBWriter,
        archive: RawArchive,
        health: HealthRegistry,
    ) -> None:
        self.settings = settings
        self.writer = writer
        self.archive = archive
        self.health = health
        self.signer = KalshiSigner(settings.kalshi_api_key_id, settings.kalshi_private_key_bytes)
        self.sequence = SequenceTracker()
        self._message_id = 1

    async def run(self) -> None:
        delay = 0.5
        while True:
            try:
                tickers = await self._discover_markets()
                await self._stream(tickers)
                delay = 0.5
            except asyncio.CancelledError:
                raise
            except SequenceGap as exc:
                await self.health.increment(self.name, "sequence_gaps")
                await self.health.error(self.name, exc)
                logger.warning("kalshi_sequence_gap_reconnect", error=str(exc))
            except Exception as exc:
                await self.health.error(self.name, exc)
                logger.exception("kalshi_collector_error")
            await self.health.increment(self.name, "reconnects")
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)

    async def _discover_markets(self) -> tuple[str, ...]:
        params = {
            "series_ticker": self.settings.kalshi_series_ticker,
            "status": "open",
            "limit": 100,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.settings.kalshi_rest_base}/markets", params=params)
            response.raise_for_status()
            payload = response.json()
        stamp = ReceiveStamp.now()
        markets = payload.get("markets", [])
        tickers: list[str] = []
        for market in markets:
            ticker = market.get("ticker")
            if not ticker:
                continue
            tickers.append(ticker)
            await self.writer.put(
                MarketSnapshot,
                {
                    "captured_at": stamp.wall_time,
                    "ticker": ticker,
                    "event_ticker": market.get("event_ticker"),
                    "series_ticker": market.get("series_ticker", self.settings.kalshi_series_ticker),
                    "status": market.get("status"),
                    "open_time": _dt(market.get("open_time")),
                    "close_time": _dt(market.get("close_time")),
                    "expiration_time": _dt(
                        market.get("latest_expiration_time") or market.get("expiration_time")
                    ),
                    "strike_type": market.get("strike_type"),
                    "floor_strike": _decimal(market.get("floor_strike")),
                    "rules_primary": market.get("rules_primary"),
                    "rules_secondary": market.get("rules_secondary"),
                    "can_close_early": market.get("can_close_early"),
                    "raw": market,
                },
            )
        await self.health.heartbeat(self.name, open_markets=len(tickers), tickers=tickers)
        return tuple(sorted(tickers))

    async def _stream(self, tickers: tuple[str, ...]) -> None:
        self.sequence.reset()
        headers = self.signer.headers("GET", WS_PATH)
        async with websockets.connect(
            self.settings.kalshi_ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_queue=8192,
        ) as websocket:
            await self._subscribe(websocket, tickers)
            await self.health.update(self.name, status="healthy")
            next_discovery = asyncio.get_running_loop().time() + self.settings.kalshi_discovery_interval_seconds
            while True:
                timeout = max(0.1, next_discovery - asyncio.get_running_loop().time())
                try:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                except TimeoutError:
                    latest = await self._discover_markets()
                    if latest != tickers:
                        logger.info("kalshi_market_set_changed", old=tickers, new=latest)
                        return
                    next_discovery = (
                        asyncio.get_running_loop().time()
                        + self.settings.kalshi_discovery_interval_seconds
                    )
                    continue
                message = orjson.loads(raw)
                await self._handle(message)

    async def _subscribe(self, websocket: Any, tickers: tuple[str, ...]) -> None:
        await self._send_subscribe(
            websocket,
            {"channels": ["cfbenchmarks_value"], "index_ids": ["BRTI"]},
        )
        await self._send_subscribe(websocket, {"channels": ["market_lifecycle_v2"]})
        if tickers:
            await self._send_subscribe(
                websocket,
                {
                    "channels": ["orderbook_delta"],
                    "market_tickers": list(tickers),
                    "use_yes_price": True,
                },
            )
            await self._send_subscribe(
                websocket,
                {"channels": ["ticker", "trade"], "market_tickers": list(tickers)},
            )

    async def _send_subscribe(self, websocket: Any, params: dict[str, Any]) -> None:
        message = {"id": self._message_id, "cmd": "subscribe", "params": params}
        self._message_id += 1
        await websocket.send(json.dumps(message))

    async def _handle(self, message: dict[str, Any]) -> None:
        stamp = ReceiveStamp.now()
        await self.archive.put("kalshi", message, stamp.wall_time)
        message_type = message.get("type", "unknown")
        sid = message.get("sid")
        sequence = message.get("seq")
        if sequence is not None and sid is not None:
            self.sequence.observe(f"{sid}", int(sequence), strict_increment=True)
        await self.health.heartbeat(self.name, last_type=message_type)

        if message_type == "cfbenchmarks_value":
            await self._handle_cfbenchmark(message, stamp)
        elif message_type in {"orderbook_snapshot", "orderbook_delta"}:
            await self._handle_book(message, stamp)
        elif message_type == "ticker":
            await self._handle_ticker(message, stamp)
        elif message_type == "trade":
            await self._handle_trade(message, stamp)
        elif message_type in {"market_lifecycle_v2", "event_lifecycle", "event_fee_update"}:
            await self._handle_lifecycle(message, stamp)
        elif message_type == "error":
            raise RuntimeError(f"Kalshi websocket error: {message.get('msg')}")

    async def _handle_cfbenchmark(self, event: dict[str, Any], stamp: ReceiveStamp) -> None:
        msg = event["msg"]
        upstream = json.loads(msg["data"])
        source_ms = int(upstream["time"])
        avg = msg.get("avg_60s_data") or {}
        quarter = msg.get("last_60s_windowed_average_15min") or {}
        await self.writer.put(
            CFBenchmarkTick,
            {
                "index_id": msg["index_id"],
                "sequence": event.get("seq"),
                "source_timestamp_ms": source_ms,
                "source_time": datetime.fromtimestamp(source_ms / 1000, tz=UTC),
                "receive_wall_time": stamp.wall_time,
                "receive_monotonic_ns": stamp.monotonic_ns,
                "value": Decimal(upstream["value"]),
                "trailing_60s_average": _decimal(avg.get("value")),
                "trailing_60s_count": avg.get("window_size"),
                "quarter_final_minute_average": _decimal(quarter.get("value")),
                "quarter_final_minute_count": quarter.get("window_size"),
                "quarter_window_start_ms": quarter.get("window_start_ts_ms"),
                "quarter_window_end_exclusive_ms": quarter.get("window_end_ts_exclusive"),
                "raw": event,
            },
        )

    async def _handle_book(self, event: dict[str, Any], stamp: ReceiveStamp) -> None:
        msg = event["msg"]
        ticker = msg["market_ticker"]
        common = {
            "market_ticker": ticker,
            "message_type": event["type"],
            "sequence": event.get("seq"),
            "source_time": _dt(msg.get("ts") or (msg.get("ts_ms", 0) / 1000 if msg.get("ts_ms") else None)),
            "receive_wall_time": stamp.wall_time,
            "receive_monotonic_ns": stamp.monotonic_ns,
            "use_yes_price": True,
            "raw": event,
        }
        if event["type"] == "orderbook_snapshot":
            for side, field in (("yes", "yes_dollars_fp"), ("no", "no_dollars_fp")):
                for price, quantity in msg.get(field, []):
                    await self.writer.put(
                        KalshiBookEvent,
                        common
                        | {
                            "book_side": side,
                            "normalized_yes_price": Decimal(price),
                            "quantity": Decimal(quantity),
                        },
                    )
        else:
            await self.writer.put(
                KalshiBookEvent,
                common
                | {
                    "book_side": msg.get("book_side") or msg.get("side"),
                    "normalized_yes_price": _decimal(
                        msg.get("price_dollars") or msg.get("price_dollars_fp")
                    ),
                    "quantity": _decimal(msg.get("delta_fp") or msg.get("delta")),
                },
            )

    async def _handle_ticker(self, event: dict[str, Any], stamp: ReceiveStamp) -> None:
        msg = event["msg"]
        await self.writer.put(
            KalshiTicker,
            {
                "market_ticker": msg["market_ticker"],
                "sequence": event.get("seq"),
                "source_time": _dt(msg.get("time") or (msg.get("ts_ms", 0) / 1000 if msg.get("ts_ms") else None)),
                "receive_wall_time": stamp.wall_time,
                "receive_monotonic_ns": stamp.monotonic_ns,
                "yes_bid": _decimal(msg.get("yes_bid_dollars")),
                "yes_ask": _decimal(msg.get("yes_ask_dollars")),
                "yes_bid_size": _decimal(msg.get("yes_bid_size_fp")),
                "yes_ask_size": _decimal(msg.get("yes_ask_size_fp")),
                "last_price": _decimal(msg.get("price_dollars")),
                "volume": _decimal(msg.get("volume_fp")),
                "open_interest": _decimal(msg.get("open_interest_fp")),
                "raw": event,
            },
        )

    async def _handle_trade(self, event: dict[str, Any], stamp: ReceiveStamp) -> None:
        msg = event["msg"]
        source_ms = msg.get("ts_ms")
        await self.writer.put(
            KalshiTrade,
            {
                "trade_id": msg.get("trade_id"),
                "market_ticker": msg["market_ticker"],
                "yes_price": Decimal(msg["yes_price_dollars"]),
                "no_price": Decimal(msg["no_price_dollars"]),
                "quantity": Decimal(msg.get("count_fp", "0")),
                "taker_outcome_side": msg.get("taker_outcome_side") or msg.get("taker_side"),
                "taker_book_side": msg.get("taker_book_side"),
                "source_time": datetime.fromtimestamp(source_ms / 1000, tz=UTC) if source_ms else None,
                "receive_wall_time": stamp.wall_time,
                "receive_monotonic_ns": stamp.monotonic_ns,
                "raw": event,
            },
        )

    async def _handle_lifecycle(self, event: dict[str, Any], stamp: ReceiveStamp) -> None:
        msg = event["msg"]
        source_seconds = msg.get("ts") or msg.get("close_ts") or msg.get("open_ts")
        await self.writer.put(
            LifecycleEvent,
            {
                "source": "kalshi",
                "message_type": event["type"],
                "sequence": event.get("seq"),
                "market_ticker": msg.get("market_ticker"),
                "event_ticker": msg.get("event_ticker")
                or (msg.get("additional_metadata") or {}).get("event_ticker"),
                "event_type": msg.get("event_type"),
                "source_time": _dt(source_seconds),
                "receive_wall_time": stamp.wall_time,
                "receive_monotonic_ns": stamp.monotonic_ns,
                "raw": event,
            },
        )
