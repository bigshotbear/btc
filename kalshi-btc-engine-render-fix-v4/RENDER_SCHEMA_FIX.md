# Render schema repair (v4)

The web service can connect to PostgreSQL, but `/api/latest` reports:

```text
relation "cfbenchmark_ticks" does not exist
```

This means the database was stamped at Alembic revision `0001` without all application tables.

Version 4 adds:

- Alembic migration `0002_repair_missing_schema`
- An idempotent startup schema repair
- A health check that lists missing tables rather than returning a vague 500 error
- The same schema guard in the standalone collector worker

## Deploy

1. Replace the GitHub repository contents with this version.
2. Commit and push to `main`.
3. In Render choose **Manual Deploy → Clear build cache & deploy**.
4. Confirm the deploy log includes:

```text
Running upgrade 0001 -> 0002, repair missing collector tables
```

5. Open `/healthz`. It should report `"schema": "complete"`.
6. Open `/api/latest`. Empty values are normal until collectors write their first records.
