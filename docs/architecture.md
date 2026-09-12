# Architecture

```text
Binance REST/WebSocket -> trader worker -> PostgreSQL snapshots -> API -> dashboard
                         |
                         +-> closed candles -> EMA -> TradeIntent
                         +-> RiskEngine -> OrderManager -> PaperBroker
                         +-> SQLAlchemy (SQLite local or PostgreSQL Docker)
```

The dashboard is an operator surface. Strategies produce intents; they do not
call Binance. `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false` are the
safe defaults. The PAPER runtime polls closed 1h Binance candles, runs one EMA
strategy, persists signals/intents/orders/fills and exposes the resulting
snapshot. The current release exposes public market data and a signed account
reader only; it does not submit orders to Binance.

Local runtime stores its database under `E:\AlgoDesk\data`. Compose overlays
replace that connection with PostgreSQL without changing Python code. The
versioned risk and strategy controls live in `E:\AlgoDesk\configs` and are
mounted read-only into the local trader container; they contain no secrets.
