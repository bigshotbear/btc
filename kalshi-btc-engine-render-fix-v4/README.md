# Kalshi BTC 15-Minute Engine — Phase 1

A read-only, production-oriented data foundation for researching Kalshi's BTC "Up or Down — 15 Minutes" markets.

## What this version does

- Discovers open `KXBTC15M` markets through Kalshi REST.
- Stores point-in-time market metadata, strike, rules, close time, and raw payloads.
- Connects to Kalshi's authenticated WebSocket.
- Records Kalshi order-book snapshots and native deltas with `use_yes_price: true`.
- Records Kalshi public trades and canonical taker direction when available.
- Records all market/event lifecycle and fee-override events.
- Records Kalshi's official live `BRTI` stream.
- Records Kalshi's official quarter-hour final-minute running average and count.
- Records Coinbase BTC-USD Level 2 updates and trades.
- Records Kraken BTC/USD Level 2 updates and trades.
- Detects Kalshi/Coinbase sequence gaps and reconnects for a clean snapshot.
- Validates Kraken's CRC32 book checksum and reconnects on mismatch.
- Stores normalized research rows in PostgreSQL.
- Archives native messages in hourly compressed JSONL files.
- Exposes a phone-friendly status dashboard.

## What it deliberately does not do

- No predictions.
- No paper orders yet.
- No real-money order placement.
- No API route capable of creating, canceling, or modifying an order.
- No claimed indicator weights or win percentages.

The first goal is clean, replayable, point-in-time data. A model built on corrupted or incomplete books is worse than no model.

## Important architecture upgrade

Kalshi now exposes a `cfbenchmarks_value` WebSocket channel. It provides:

- Raw BRTI values roughly once per second.
- A trailing 60-second average.
- During the final minute before each quarter hour, the exact quarter-hour running average and observation count.

This means the engine can save the official settlement reference stream directly. Coinbase and Kraken remain essential for independent lead/lag, proxy-error, order-flow, and regime research, but they are no longer treated as the primary settlement source.

Official references:

- Kalshi WebSocket: https://docs.kalshi.com/getting_started/quick_start_websockets
- CF Benchmarks feed: https://docs.kalshi.com/websockets/cfbenchmarks-value
- Order-book unified pricing: https://docs.kalshi.com/getting_started/order_direction
- Coinbase channels: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels
- Kraken book: https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book
- Kraken checksum: https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2

## Repository layout

```text
src/btc_engine/
├── api/                 # FastAPI status dashboard
├── auth/                # Kalshi RSA-PSS signing
├── collectors/          # Kalshi, Coinbase, Kraken collectors
├── core/                # clocks, sequence checks, settlement math, books
├── research/            # pre-registered confluence hypotheses
├── storage/             # SQLAlchemy models, batch writer, raw archive
└── worker.py            # always-on collector process
```

## Local setup

### 1. Create a Kalshi demo API key

Start in Kalshi's demo environment. Production and demo credentials are separate.

Save the downloaded private key under:

```text
secrets/kalshi_private_key
```

Never commit the key.

### 2. Configure

```bash
cp .env.example .env
```

Set:

```dotenv
KALSHI_ENV=demo
KALSHI_API_KEY_ID=your-key-id
KALSHI_PRIVATE_KEY_PATH=/run/secrets/kalshi_private_key
```

### 3. Run

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

### 4. Run tests

```bash
python -m pip install -e '.[dev]'
pytest -q
```

## Railway deployment

Use one GitHub repository to create three Railway services:

1. PostgreSQL
2. `api`
3. `worker`

Both app services point at the same GitHub repository and PostgreSQL `DATABASE_URL`.

### API service

Start command:

```bash
alembic upgrade head && uvicorn btc_engine.api.main:app --host 0.0.0.0 --port $PORT
```

Generate a public domain for this service.

### Worker service

Start command:

```bash
alembic upgrade head && python -m btc_engine.worker
```

Do not generate a public domain for the worker.

Attach a Railway volume to the worker at `/data` so compressed raw archives survive redeployments.

### Shared variables

```dotenv
APP_ENV=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
RAW_DATA_DIR=/data/raw
RAW_ARCHIVE_ENABLED=true
KALSHI_ENV=demo
KALSHI_API_KEY_ID=...
KALSHI_PRIVATE_KEY_PEM=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
KALSHI_SERIES_TICKER=KXBTC15M
KALSHI_ENABLE=true
COINBASE_ENABLE=true
KRAKEN_ENABLE=true
```

Keep the Kalshi private key in Railway's secret variables. Do not expose it in browser code or logs.

Full steps: [docs/RAILWAY.md](docs/RAILWAY.md)

## Raw archive format

Hourly files are written to:

```text
/data/raw/{source}/YYYY/MM/DD/HH.jsonl.gz
```

Each line contains:

```json
{
  "collector_receive_time": "2026-07-23T12:00:00.123456+00:00",
  "source": "kalshi",
  "payload": {}
}
```

PostgreSQL stores normalized, query-friendly records. The compressed archive preserves the original native messages for deterministic replay.

## Four-clock policy

Normalized rows store:

1. Source event time, when available.
2. Collector wall-clock receive time.
3. Collector monotonic receive timestamp.
4. Database enqueue time.

Each normalized row also carries `db_batch_id`. The `db_batch_commits` ledger records the batch commit start, successful commit completion time, row count, tables, and duration, so database persistence latency is auditable without pretending enqueue time equals commit time.

## Phase 2 entry criteria

Do not build the probability model until:

- The worker runs continuously for several days.
- No unexplained sequence/checksum failures remain.
- BRTI final-minute counts reliably reach 60.
- Open-market discovery rolls correctly every 15 minutes.
- Raw archives survive a redeploy.
- PostgreSQL storage growth is measured.
- Collector receive-latency distributions are visible.

Then add:

1. Data-quality report.
2. Deterministic event replay.
3. Simple target-distance / path-average baseline.
4. Leakage-free walk-forward calibration.
5. Stateful paper execution simulator.

## Security

- Read-only API surface.
- No order endpoint dependency.
- No private key in the frontend.
- Use Kalshi demo credentials first.
- Rotate keys if they are ever pasted into a chat, issue, or commit.

## Render schema repair note (v4)

If an older deployment shows `relation "cfbenchmark_ticks" does not exist`, deploy this version. Migration `0002` and the startup schema guard create all missing tables without deleting existing data. See `RENDER_SCHEMA_FIX.md`.
