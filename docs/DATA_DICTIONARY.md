# Data dictionary

## `market_snapshots`
Point-in-time REST market records. Never overwrite older rows.

## `cfbenchmark_ticks`
Official BRTI values from Kalshi's CF Benchmarks WebSocket channel. The quarter-hour fields are populated only during the final minute.

## `kalshi_book_events`
Native snapshot levels and deltas. With `use_yes_price=true`, YES-side levels are YES bids and NO-side levels represent the opposite side on the same YES price scale.

## `kalshi_tickers`
Top-of-book and market statistics emitted by the ticker channel.

## `kalshi_trades`
Public Kalshi executions with taker direction fields when supplied.

## `lifecycle_events`
Market creation, activation, deactivation, close-date updates, metadata updates, determination, settlement, and fee overrides.

## `exchange_book_events`
Coinbase and Kraken Level 2 changes. Coinbase quantities are replacement quantities, not deltas. Kraken quantities are replacement quantities and zero removes a level.

## `exchange_trades`
Coinbase and Kraken trades. Coinbase's raw `side` is maker side and is inverted into `aggressor_side`; Kraken's v2 trade side is taker side.

## `feed_health_events`
Periodic snapshots of collector state, reconnects, sequence gaps, and last error.

## `research_hypotheses`
A ledger for feature and interaction experiments so repeated testing is visible and the final holdout is protected.


## `db_batch_commits`
A commit ledger keyed by the `db_batch_id` stored on normalized rows. It records commit start, successful completion, duration, row count, and table counts.
