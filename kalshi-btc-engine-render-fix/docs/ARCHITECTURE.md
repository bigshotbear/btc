# Architecture

```text
Kalshi REST ───────────────┐
Kalshi WS orderbook/trades ├─> worker ─> PostgreSQL normalized tables
Kalshi WS official BRTI ───┤          └─> hourly gzip native archives
Coinbase L2/trades ────────┤
Kraken L2/trades ──────────┘

PostgreSQL ─> FastAPI ─> mobile status dashboard
```

## Safety boundary

The worker has only market-data functionality. No code path creates, amends, cancels, or settles orders.

## Data priority

1. Official Kalshi BRTI and final-minute running average.
2. Point-in-time contract metadata and lifecycle.
3. Executable Kalshi book and trades.
4. Coinbase/Kraken microstructure.
5. Future derived features.

## Recovery behavior

- Kalshi sequence gap: disconnect and resubscribe, receiving a fresh snapshot.
- Coinbase sequence gap: reconnect and resubscribe to guaranteed-delivery Level 2.
- Kraken checksum mismatch: reconnect and request a new snapshot.
- Market ticker changes: reconnect Kalshi subscriptions with the new open ticker set.
