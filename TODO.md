# AlgoDesk TODO

## Done in v0.1.0

- [x] React/Vite dashboard on the HD
- [x] Operations Desk with 5 bot states
- [x] Search and bot inspector interactions
- [x] Paper mode and Binance connection status UI
- [x] Hard stop interlock with `ENABLE` reactivation
- [x] Safe environment defaults and architecture plan

## Next implementation gates

- [ ] Add FastAPI service and typed read-only endpoints
- [ ] Add SQLAlchemy/Alembic models and PostgreSQL healthcheck
- [ ] Add PaperBroker with idempotent order state machine
- [ ] Add Binance Spot adapter (market data first)
- [ ] Add EMA/ATR strategy and candle close handling
- [ ] Add backtest fees, slippage, metrics and buy-and-hold comparison
- [ ] Add Docker Compose local/VPS overlays
- [ ] Add pytest + frontend CI checks
- [ ] Run Testnet soak test before any live-candidate review
