from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import orjson
import websockets
from dateutil.parser import isoparse

from btc_engine.config import Settings
from btc_engine.core.clock import ReceiveStamp
from btc_engine.core.health import HealthRegistry
from btc_engine.core.sequence import SequenceGap, SequenceTracker
from btc_engine.storage.models import ExchangeBookEvent, ExchangeTrade
from btc_engine.storage.raw_archive import RawArchive
from btc_engine.storage.writer import BatchDBWriter

from btc_engine.logging import get_logger

logger = get_logger(__name__)


class CoinbaseCollector:
    name = "coinbase"
    url = "wss://advanced-trade-ws.coinbase.com"

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
        self.sequence = SequenceTracker()

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
                logger.warning("coinbase_sequence_gap_reconnect", error=str(exc))
            except Exception as exc:
                await self.health.error(self.name, exc)
                logger.exception("coinbase_collector_error")
            await self.health.increment(self.name, "reconnects")
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)

    async def _stream(self) -> None:
        self.sequence.reset()
        async with websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_queue=8192,
        ) as websocket:
            product = self.settings.coinbase_product_id
            for channel in ("level2", "market_trades"):
                await websocket.send(
                    orjson.dumps(
                        {"type": "subscribe", "product_ids": [product], "channel": channel}
                    ).decode()
                )
            await websocket.send(orjson.dumps({"type": "subscribe", "channel": "heartbeats"}).decode())
            await self.health.update(self.name, status="healthy")
            async for raw in websocket:
                message = orjson.loads(raw)
                await self._handle(message)

    async def _handle(self, message: dict[str, Any]) -> None:
        stamp = ReceiveStamp.now()
        await self.archive.put("coinbase", message, stamp.wall_time)
        channel = message.get("channel", "unknown")
        sequence = message.get("sequence_num")
        if sequence is not None:
            self.sequence.observe(channel, int(sequence), strict_increment=True)
        await self.health.heartbeat(self.name, channel=channel)

        if channel in {"l2_data", "level2"}:
            for event in message.get("events", []):
                product = event.get("product_id", self.settings.coinbase_product_id)
                event_type = event.get("type", "update")
                for update in event.get("updates", []):
                    source_time = isoparse(update["event_time"]).astimezone(UTC)
                    side = "bid" if str(update["side"]).lower() == "bid" else "ask"
                    await self.writer.put(
                        ExchangeBookEvent,
                        {
                            "exchange": "coinbase",
                            "symbol": product,
                            "message_type": event_type,
                            "side": side,
                            "price": Decimal(update["price_level"]),
                            "quantity": Decimal(update["new_quantity"]),
                            "sequence": sequence,
                            "checksum": None,
                            "source_time": source_time,
                            "receive_wall_time": stamp.wall_time,
                            "receive_monotonic_ns": stamp.monotonic_ns,
                            "raw": update,
                        },
                    )
        elif channel == "market_trades":
            for event in message.get("events", []):
                for trade in event.get("trades", []):
                    raw_side = str(trade.get("side", "")).upper()
                    # Coinbase documents this as maker side, so aggressor is the opposite.
                    aggressor = "sell" if raw_side == "BUY" else "buy" if raw_side == "SELL" else None
                    await self.writer.put(
                        ExchangeTrade,
                        {
                            "exchange": "coinbase",
                            "symbol": trade.get("product_id", self.settings.coinbase_product_id),
                            "trade_id": str(trade.get("trade_id")) if trade.get("trade_id") else None,
                            "price": Decimal(trade["price"]),
                            "quantity": Decimal(trade["size"]),
                            "aggressor_side": aggressor,
                            "raw_side": raw_side,
                            "source_time": isoparse(trade["time"]).astimezone(UTC),
                            "receive_wall_time": stamp.wall_time,
                            "receive_monotonic_ns": stamp.monotonic_ns,
                            "raw": trade,
                        },
                    )
