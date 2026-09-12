# Architecture

```text
Binance REST/WebSocket -> FastAPI trader -> read-only dashboard
                         |
                         +-> PAPER domain / risk engine / backtest
                         +-> SQLAlchemy (SQLite local or PostgreSQL Docker)
```

The dashboard is an operator surface. Strategies produce intents; they do not
call Binance. `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false` are the
safe defaults. The current release exposes public market data and a signed
account reader only; it does not submit orders.

Local runtime stores its database under `E:\AlgoDesk\data`. Compose overlays
replace that connection with PostgreSQL without changing Python code.
