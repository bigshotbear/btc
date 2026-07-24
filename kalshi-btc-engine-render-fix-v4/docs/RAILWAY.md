# Railway deployment

## 1. Put the repository on GitHub

Create a private GitHub repository and upload this project. Confirm that `.env`, `.key`, and `.pem` files are not committed.

## 2. Create Railway project

- New Project
- Deploy from GitHub repo
- Add PostgreSQL from `+ New` → `Database` → `PostgreSQL`

## 3. Configure API service

Use the GitHub repository as the source.

Start command:

```bash
alembic upgrade head && uvicorn btc_engine.api.main:app --host 0.0.0.0 --port $PORT
```

Add `DATABASE_URL` as a reference to the PostgreSQL service. Generate a public domain.

## 4. Configure worker service

Add the same GitHub repository as a second service.

Start command:

```bash
alembic upgrade head && python -m btc_engine.worker
```

Do not give this service a public domain.

Attach a persistent volume mounted at `/data`.

## 5. Add secrets

Add the variables from `.env.example`. For Railway, the easiest private-key setup is `KALSHI_PRIVATE_KEY_PEM` with newline characters represented as `\n`.

Use demo credentials until the collection system has run cleanly.

## 6. Verify

- API `/healthz` returns `{"status":"ok"}`.
- Dashboard shows an official BRTI value.
- During the final minute, the BRTI average shows `1/60` through `60/60`.
- Coinbase and Kraken last trades update.
- Worker logs contain no repeated checksum or sequence errors.
- The Railway volume contains `/data/raw/...jsonl.gz` files.
