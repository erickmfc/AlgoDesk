# AlgoDesk TODO

## Done in v0.1.0

- [x] Next.js dashboard on the HD
- [x] Operations Desk with 5 bot states
- [x] Search and bot inspector interactions
- [x] Paper mode and Binance connection status UI
- [x] Hard stop interlock with `ENABLE` reactivation
- [x] Safe environment defaults and architecture plan
- [x] Public Binance Spot ticker adapter with CORS-safe read-only endpoint
- [x] Public Binance Spot WebSocket mini-ticker with heartbeat and reconnect backoff
- [x] Optional signed, server-side, read-only Binance account summary endpoint
- [x] EMA/ATR strategy primitives and backtest with fees/slippage
- [x] Extended research metrics and buy-and-hold comparison for the demo run
- [x] PostgreSQL-ready SQLAlchemy schema for core trading records
- [x] Typed settings, local SQLite persistence bootstrap and Docker healthchecks
- [x] Real closed Binance Spot candles for research backtest
- [x] Alembic bootstrap migration and CI quality gates
- [x] PAPER candle-close runner through Strategy → Risk → OrderManager → Broker
- [x] Persist PAPER signals, intents, orders, events, fills and snapshots
- [x] Read-only account reconciliation primitives and User Data Stream adapter
- [x] Separate `api` and `trader` Compose services with shared PostgreSQL snapshots
- [x] Persisted runtime summaries/events for a stateless API process
- [x] Binance Spot Testnet broker gate with exchange filters and remote idempotency lookup
- [x] User Data Stream keepalive, reconnect hard stop and periodic reconciliation on Testnet
- [x] Explicit in-sample/validation/out-of-sample research splits
- [x] Stop/take-profit, spread, latency and partial-fill abstractions in the backtest

## Next implementation gates

- [x] True walk-forward parameter selection using validation-only choice and untouched OOS scoring
- [x] Restore Testnet base/quote balances and average entry price from Binance fills, fail-closed on mismatch
- [x] Fail-closed market-cycle alert/pause policy for the long-running worker
- [ ] Run Testnet soak test before any live-candidate review
- [x] Add repeatable read-only runtime verification for health, readiness, market data, paper state and backtest
- [x] Add read-only multi-cycle PAPER/Testnet soak runner with fail-closed mode and credential checks
- [x] Make the base Docker Compose override the host SQLite URL with the internal PostgreSQL URL
