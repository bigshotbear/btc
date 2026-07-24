from __future__ import annotations

import asyncio
import json
import zlib
from datetime import UTC
from decimal import Decimal
from typing import Any

import orjson
import websockets
from dateutil.parser import isoparse

from btc_engine.config import Settings
from btc_engine.core.clock import ReceiveStamp
from btc_engine.core.health import HealthRegistry
from btc_engine.core.sequence import SequenceGap
from btc_engine.storage.models import ExchangeBookEvent, ExchangeTrade
from btc_engine.storage.raw_archive import RawArchive
from btc_engine.storage.writer import BatchDBWriter

from btc_engine.logging import get_logger

logger = get_logger(__name__)


def _checksum_component(value: Decimal) -> str:
    text = format(value, "f").replace(".", "").lstrip("0")
    return text or "0"


class KrakenBook:
    def __init__(self, depth: int) -> None:
        self.depth = depth
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}

    def apply(self, side: str, price: Decimal, quantity: Decimal) -> None:
        levels = self.bids if side == "bid" else self.asks
        if quantity == 0:
            levels.pop(price, None)
        else:
            levels[price] = quantity

    def replace(self, bids: list[dict[str, Any]], asks: list[dict[str, Any]]) -> None:
        self.bids = {Decimal(str(x["price"])): Decimal(str(x["qty"])) for x in bids}
        self.asks = {Decimal(str(x["price"])): Decimal(str(x["qty"])) for x in asks}
        self._truncate()

    def _truncate(self) -> None:
        if len(self.bids) > self.depth:
            keep = set(sorted(self.bids, reverse=True)[: self.depth])
            self.bids = {p: self.bids[p] for p in keep}
        if len(self.asks) > self.depth:
            keep = set(sorted(self.asks)[: self.depth])
            self.asks = {p: self.asks[p] for p in keep}

    def checksum(self) -> int:
        parts: list[str] = []
        for price in sorted(self.asks)[:10]:
            parts.append(_checksum_component(price))
            parts.append(_checksum_component(self.asks[price]))
        for price in sorted(self.bids, reverse=True)[:10]:
            parts.append(_checksum_component(price))
            parts.append(_checksum_component(self.bids[price]))
        return zlib.crc32("".join(parts).encode()) & 0xFFFFFFFF


class KrakenCollector:
    name = "kraken"
    url = "wss://ws.kraken.com/v2"

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
        self.book = KrakenBook(settings.kraken_book_depth)

    async def run(self) -> None:
        delay = 0.5
        while True:
            try:
                await self._stream()
                delay = 0.5
            except asyncio.CancelledError:
                raise
            except SequenceGap as exc:
                await self.health.increment(self.name, "sequence_gaps")
                await self.health.error(self.name, exc)
                logger.warning("kraken_checksum_reconnect", error=str(exc))
            except Exception as exc:
                await self.health.error(self.name, exc)
                logger.exception("kraken_collector_error")
            await self.health.increment(self.name, "reconnects")
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)

    async def _stream(self) -> None:
        self.book = KrakenBook(self.settings.kraken_book_depth)
        async with websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_queue=8192,
        ) as websocket:
            symbol = self.settings.kraken_symbol
            await websocket.send(
                orjson.dumps(
                    {
                        "method": "subscribe",
                        "params": {
                            "channel": "book",
                            "symbol": [symbol],
                            "depth": self.settings.kraken_book_depth,
                            "snapshot": True,
                        },
                    }
                ).decode()
            )
            await websocket.send(
                orjson.dumps(
                    {
                        "method": "subscribe",
                        "params": {"channel": "trade", "symbol": [symbol], "snapshot": False},
                    }
                ).decode()
            )
            await self.health.update(self.name, status="healthy")
            async for raw in websocket:
                archive_message = orjson.loads(raw)
                message = json.loads(raw, parse_float=Decimal)
                await self._handle(message, archive_message)

    async def _handle(self, message: dict[str, Any], archive_message: dict[str, Any]) -> None:
        stamp = ReceiveStamp.now()
        await self.archive.put("kraken", archive_message, stamp.wall_time)
        channel = message.get("channel")
        if not channel:
            if message.get("success") is False:
                raise RuntimeError(f"Kraken subscription failed: {message.get('error')}")
            return
        await self.health.heartbeat(self.name, channel=channel)
        if channel == "book":
            await self._handle_book(message, stamp)
        elif channel == "trade":
            await self._handle_trade(message, stamp)

    async def _handle_book(self, message: dict[str, Any], stamp: ReceiveStamp) -> None:
        event_type = message.get("type", "update")
        for data in message.get("data", []):
            symbol = data.get("symbol", self.settings.kraken_symbol)
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            if event_type == "snapshot":
                self.book.replace(bids, asks)
            else:
                for item in bids:
                    self.book.apply("bid", Decimal(str(item["price"])), Decimal(str(item["qty"])))
                for item in asks:
                    self.book.apply("ask", Decimal(str(item["price"])), Decimal(str(item["qty"])))
                self.book._truncate()
            checksum = int(data["checksum"]) if data.get("checksum") is not None else None
            if checksum is not None and self.book.checksum() != checksum:
                raise SequenceGap(
                    f"kraken checksum expected {checksum}, calculated {self.book.checksum()}"
                )
            for side, entries in (("bid", bids), ("ask", asks)):
                for item in entries:
                    source_time = isoparse(str(data["timestamp"])).astimezone(UTC)
                    await self.writer.put(
                        ExchangeBookEvent,
                        {
                            "exchange": "kraken",
                            "symbol": symbol,
                            "message_type": event_type,
                            "side": side,
                            "price": Decimal(str(item["price"])),
                            "quantity": Decimal(str(item["qty"])),
                            "sequence": None,
                            "checksum": checksum,
                            "source_time": source_time,
                            "receive_wall_time": stamp.wall_time,
                            "receive_monotonic_ns": stamp.monotonic_ns,
                            "raw": {k: str(v) if isinstance(v, Decimal) else v for k, v in item.items()},
                        },
                    )

    async def _handle_trade(self, message: dict[str, Any], stamp: ReceiveStamp) -> None:
        for trade in message.get("data", []):
            await self.writer.put(
                ExchangeTrade,
                {
                    "exchange": "kraken",
                    "symbol": trade.get("symbol", self.settings.kraken_symbol),
                    "trade_id": str(trade.get("trade_id")) if trade.get("trade_id") else None,
                    "price": Decimal(str(trade["price"])),
                    "quantity": Decimal(str(trade["qty"])),
                    "aggressor_side": trade.get("side"),
                    "raw_side": trade.get("side"),
                    "source_time": isoparse(str(trade["timestamp"])).astimezone(UTC),
                    "receive_wall_time": stamp.wall_time,
                    "receive_monotonic_ns": stamp.monotonic_ns,
                    "raw": {
                        k: str(v) if isinstance(v, Decimal) else v for k, v in trade.items()
                    },
                },
            )
