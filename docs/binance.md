# Binance integration boundary

The first external integration is Binance Spot market data. `BinancePublicClient` reads `/api/v3/ticker/price` and `BinanceMarketStream` consumes combined `@miniTicker` streams through the internal `/ws/market` endpoint. The stream has a 20-second heartbeat and exponential reconnect backoff up to 30 seconds.

`/api/account/summary` is an optional signed call to `/api/v3/account`. The
adapter also contains open-order, all-order and trade/fill reads, Spot
limit-order/cancel/query methods and the Spot User Data Stream listen-key
lifecycle. The external
broker is mode-gated: it can target Binance Spot Testnet only in
`TRADING_MODE=testnet`, and LIVE additionally requires
`LIVE_TRADING_ENABLED=true`. API keys are read from server-side environment
variables and never returned to the dashboard.

The adapter uses official REST and WebSocket interfaces, reads current
`exchangeInfo` filters before external orders, queries `clientOrderId` before
submission, never retries an ambiguous request, reconnects user streams,
keeps the listen key alive and reconciles balances, open orders, managed order
history and fills after reconnects and on a periodic Testnet schedule. A
divergence pauses the worker and requires reconciliation;
the Testnet soak remains a prerequisite for any live-candidate review.

At Testnet startup, the worker restores the configured symbol's base and quote
balances and rebuilds the remaining average entry price from Binance
`myTrades`. It refuses to trade if that history cannot reproduce the current
base balance. Confirmed execution reports are applied once by cumulative fill
quantity; the local state remains paused on malformed stream messages or a
reconciliation mismatch.

No secret belongs in the frontend, Git or logs. The intended key permissions are read and Spot Trading only, with withdrawals, Futures and Margin disabled. `LIVE_TRADING_ENABLED=false` remains a second application-level lock.
