# AlgoDesk TODO

## Done in v0.1.0

- [x] React/Vite dashboard on the HD
- [x] Operations Desk with 5 bot states
- [x] Search and bot inspector interactions
- [x] Paper mode and Binance connection status UI
- [x] Hard stop interlock with `ENABLE` reactivation
- [x] Safe environment defaults and architecture plan
- [x] Public Binance Spot ticker adapter with CORS-safe read-only endpoint
- [x] EMA/ATR strategy primitives and backtest with fees/slippage
- [x] PostgreSQL-ready SQLAlchemy schema for core trading records

## Next implementation gates

- [ ] Persist PAPER candles, intents, orders and portfolio snapshots in PostgreSQL
- [ ] Add authenticated, server-side, read-only Binance account summary
- [ ] Add Binance Spot WebSocket stream, reconnect and stale-data monitoring
- [ ] Wire EMA/ATR strategy signals to the PAPER broker and candle-close scheduler
- [ ] Add buy-and-hold comparison and walk-forward backtest splits
- [ ] Add PostgreSQL healthcheck, migrations and reconciliation telemetry
- [ ] Run Testnet soak test before any live-candidate review
