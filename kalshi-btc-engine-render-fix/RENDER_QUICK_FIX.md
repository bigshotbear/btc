# Render quick fix

The dashboard page can load while `/api/latest` still fails. The two common causes are:

1. `DATABASE_URL` is missing or points to an unavailable database.
2. The Alembic migration was not run, so the tables do not exist.

The dashboard also stays empty unless a collector process is running.

## Temporary free-Render demo mode

Use one Render Web Service with these environment variables:

```env
APP_ENV=production
DATABASE_URL=<Render Postgres internal URL>
RUN_COLLECTORS_IN_API=true
RAW_ARCHIVE_ENABLED=false
KALSHI_ENABLE=false
COINBASE_ENABLE=true
KRAKEN_ENABLE=true
```

The included Dockerfile now runs `alembic upgrade head` before starting FastAPI.

After deployment:

- `/healthz` must return JSON with `"status":"ok"`.
- `/api/latest` must return JSON, even when there is a backend error.
- Coinbase and Kraken values should begin appearing after the embedded worker connects.

`KALSHI_ENABLE=false` is required until valid Kalshi demo credentials are added. The Kalshi collector requires an API key and RSA private key even for its live WebSocket channels.

## Production mode

Do not use embedded collectors for 24/7 production. Set:

```env
RUN_COLLECTORS_IN_API=false
```

Run a separate always-on worker using:

```bash
python -m btc_engine.worker
```

Give the API and worker the same `DATABASE_URL`. Add Kalshi credentials to the worker only, then set `KALSHI_ENABLE=true`.
