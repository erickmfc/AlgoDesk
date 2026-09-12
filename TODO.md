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

## Next implementation gates

- [ ] Persist PAPER candles, intents, orders and portfolio snapshots in PostgreSQL
- [ ] Add Binance User Data Stream, account reconciliation and stale-data pause
- [ ] Wire EMA/ATR strategy signals to the PAPER broker and candle-close scheduler
- [ ] Add buy-and-hold comparison and walk-forward backtest splits
- [ ] Add Alembic migrations and reconciliation telemetry
- [ ] Run Testnet soak test before any live-candidate review
