from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import desc, select, text
from sqlalchemy.exc import SQLAlchemyError

from btc_engine.config import get_settings
from btc_engine.logging import configure_logging
from btc_engine.storage.database import create_engine, create_session_factory
from btc_engine.worker import async_main as run_worker
from btc_engine.storage.models import (
    CFBenchmarkTick,
    ExchangeTrade,
    FeedHealthEvent,
    KalshiTicker,
    MarketSnapshot,
)

settings = get_settings()
configure_logging(settings.log_level)
engine = create_engine(settings)
sessions = create_session_factory(engine)


def serialise_row(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, Decimal):
            value = str(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        result[column.name] = value
    return result


@asynccontextmanager
async def lifespan(_: FastAPI):
    collector_task: asyncio.Task | None = None
    if settings.run_collectors_in_api:
        collector_task = asyncio.create_task(run_worker(), name="embedded-collector-worker")
    try:
        yield
    finally:
        if collector_task is not None:
            collector_task.cancel()
            await asyncio.gather(collector_task, return_exceptions=True)
        await engine.dispose()


app = FastAPI(title="Kalshi BTC Engine — Phase 1", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "collectors_in_api": settings.run_collectors_in_api,
            "kalshi_enabled": settings.kalshi_enable,
            "coinbase_enabled": settings.coinbase_enable,
            "kraken_enabled": settings.kraken_enable,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unavailable",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )


@app.get("/api/latest")
async def latest():
    try:
        async with sessions() as session:
            brti = await session.scalar(
                select(CFBenchmarkTick).where(CFBenchmarkTick.index_id == "BRTI").order_by(desc(CFBenchmarkTick.id)).limit(1)
            )
            market = await session.scalar(select(MarketSnapshot).order_by(desc(MarketSnapshot.id)).limit(1))
            ticker = await session.scalar(select(KalshiTicker).order_by(desc(KalshiTicker.id)).limit(1))
            coinbase = await session.scalar(
                select(ExchangeTrade)
                .where(ExchangeTrade.exchange == "coinbase")
                .order_by(desc(ExchangeTrade.id))
                .limit(1)
            )
            kraken = await session.scalar(
                select(ExchangeTrade)
                .where(ExchangeTrade.exchange == "kraken")
                .order_by(desc(ExchangeTrade.id))
                .limit(1)
            )
            health_rows = (
                await session.scalars(
                    select(FeedHealthEvent).order_by(desc(FeedHealthEvent.id)).limit(20)
                )
            ).all()
        latest_health: dict[str, Any] = {}
        for row in health_rows:
            latest_health.setdefault(row.feed, serialise_row(row))
        return {
            "status": "ok",
            "phase": "collection_only",
            "trading_enabled": False,
            "collectors_in_api": settings.run_collectors_in_api,
            "brti": serialise_row(brti),
            "market": serialise_row(market),
            "kalshi_ticker": serialise_row(ticker),
            "coinbase_trade": serialise_row(coinbase),
            "kraken_trade": serialise_row(kraken),
            "feeds": latest_health,
        }
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "hint": "Check DATABASE_URL and run: alembic upgrade head",
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )


DASHBOARD = """
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTC Engine — Phase 1</title><style>
body{font-family:system-ui;background:#f4f6f8;color:#17202a;margin:0}.wrap{max-width:780px;margin:auto;padding:18px}
.card{background:white;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 3px 16px #00000012}
h1{font-size:24px}.muted{color:#69737d}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.value{font-size:25px;font-weight:750}.ok{color:#087f5b}.warn{color:#b26a00}code{font-size:12px;word-break:break-all}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap"><h1>Kalshi BTC Engine</h1>
<p class="muted">Phase 1: read-only collection and feed verification. No order-placement code exists.</p>
<div class="card"><div class="grid"><div><div class="muted">Official BRTI</div><div id="brti" class="value">—</div></div>
<div><div class="muted">Final-minute average</div><div id="avg" class="value">—</div></div></div></div>
<div class="card"><div class="muted">Current Kalshi market</div><div id="market" class="value">—</div><div id="quote">—</div></div>
<div class="card"><div class="grid"><div><div class="muted">Coinbase last trade</div><div id="coinbase" class="value">—</div></div>
<div><div class="muted">Kraken last trade</div><div id="kraken" class="value">—</div></div></div></div>
<div class="card"><div class="muted">Collector health</div><div id="feeds">Loading…</div></div>
<div class="card"><div class="muted">Last refresh</div><div id="refresh">—</div></div>
</div><script>
const money=x=>x==null?'—':Number(x).toLocaleString(undefined,{style:'currency',currency:'USD'});
async function refresh(){try{
const r=await fetch('/api/latest',{cache:'no-store'});
const raw=await r.text();
let d;try{d=JSON.parse(raw)}catch(_){throw new Error(`Backend returned ${r.status}: ${raw.slice(0,180)}`)}
if(!r.ok||d.status==='error'){throw new Error(`${d.error_type||'Backend error'}: ${d.message||'Unknown error'}${d.hint?' — '+d.hint:''}`)}
document.querySelector('#brti').textContent=money(d.brti?.value);
document.querySelector('#avg').textContent=d.brti?.quarter_final_minute_average?money(d.brti.quarter_final_minute_average)+' ('+d.brti.quarter_final_minute_count+'/60)':'Outside final minute';
document.querySelector('#market').textContent=d.market?.ticker||'No open market discovered';
document.querySelector('#quote').textContent=d.kalshi_ticker?`YES ${money(d.kalshi_ticker.yes_bid)} bid / ${money(d.kalshi_ticker.yes_ask)} ask`:'—';
document.querySelector('#coinbase').textContent=money(d.coinbase_trade?.price);
document.querySelector('#kraken').textContent=money(d.kraken_trade?.price);
document.querySelector('#feeds').innerHTML=Object.entries(d.feeds||{}).map(([k,v])=>`<div><b>${k}</b>: <span class="${v.status==='healthy'?'ok':'warn'}">${v.status}</span></div>`).join('')||'API is connected, but no collector records exist yet.';
document.querySelector('#refresh').textContent=new Date().toLocaleString();
}catch(e){document.querySelector('#feeds').textContent=e.message||String(e);document.querySelector('#refresh').textContent=new Date().toLocaleString()}}
refresh();setInterval(refresh,2000);
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return DASHBOARD


def run() -> None:
    uvicorn.run("btc_engine.api.main:app", host="0.0.0.0", port=settings.port)
