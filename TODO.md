# AlgoDesk TODO

## Done in v0.1.0

- [x] React/Vite dashboard on the HD
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

## Next implementation gates

- [ ] Add automatic User Data Stream keepalive/reconciliation task and stale-data pause
- [ ] Add explicit in-sample/validation/out-of-sample and walk-forward backtest splits
- [ ] Add stop/take-profit, spread, latency and partial-fill abstractions to PAPER
- [ ] Run Testnet soak test before any live-candidate review
