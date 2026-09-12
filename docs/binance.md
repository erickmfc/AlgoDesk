# Binance integration boundary

The first external integration is Binance Spot market data. `BinancePublicClient` reads `/api/v3/ticker/price` and `BinanceMarketStream` consumes combined `@miniTicker` streams through the internal `/ws/market` endpoint. The stream has a 20-second heartbeat and exponential reconnect backoff up to 30 seconds.

`/api/account/summary` is an optional signed, read-only call to `/api/v3/account`. The adapter also contains read-only open-order/trade reads and the Spot User Data Stream listen-key lifecycle for the reconciliation gate. API keys are read from server-side environment variables, never returned to the dashboard, and no order-writing method exists in this adapter.

The adapter must use official REST and WebSocket interfaces, read current `exchangeInfo` filters at runtime, back off on rate limits, reconnect user streams, and reconcile after reconnects. The latter two account-stream gates remain a prerequisite for Testnet/LIVE.

No secret belongs in the frontend, Git or logs. The intended key permissions are read and Spot Trading only, with withdrawals, Futures and Margin disabled. `LIVE_TRADING_ENABLED=false` remains a second application-level lock.
