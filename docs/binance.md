# Binance integration boundary

The first external integration is Binance Spot market data. `BinancePublicClient` reads `/api/v3/ticker/price` and `BinanceMarketStream` consumes combined `@miniTicker` streams through the internal `/ws/market` endpoint. The stream has a 20-second heartbeat and exponential reconnect backoff up to 30 seconds. Retry-safe REST reads back off on HTTP 429 twice with a capped delay; order submission and cancellation never retry automatically.

`/api/account/summary` is an optional signed call to `/api/v3/account`. The
adapter also contains open-order, all-order and trade/fill reads, Spot
limit-order/cancel/query methods and authenticated User Data Stream adapters.
On current Spot Testnet, the account stream uses the signed WebSocket API
subscription (the legacy REST listen-key adapter remains available for
mainnet-compatible streams). The external
broker is mode-gated: it can target Binance Spot Testnet only in
`TRADING_MODE=testnet`, and LIVE additionally requires
`LIVE_TRADING_ENABLED=true`. API keys are read from server-side environment
variables and never returned to the dashboard.

The adapter uses official REST and WebSocket interfaces, reads current
`exchangeInfo` filters before external orders, queries `clientOrderId` before
submission, never retries an ambiguous request, reconnects the account stream
(and keeps a legacy listen key alive where that transport is used), and
reconciles balances, open orders, managed order history and fills after
reconnects and on a periodic Testnet schedule. A
divergence pauses the worker and requires reconciliation;
the Testnet soak remains a prerequisite for any live-candidate review.

At Testnet startup, the worker restores the configured symbol's base and quote
balances and rebuilds the remaining average entry price from Binance
`myTrades`. When a clean Testnet account has the standard Binance virtual seed
with no matching fills, the worker marks that inherited balance at the first
live Spot mark for the session; this establishes a zero-PnL session baseline,
not a claim about historical cost. If fills do exist but cannot reproduce the
current balance, startup remains paused rather than guessing. Confirmed
execution reports are applied once by cumulative fill quantity; the local
state remains paused on malformed stream messages or a reconciliation
mismatch.

No secret belongs in the frontend, Git or logs. The intended key permissions are read and Spot Trading only, with withdrawals, Futures and Margin disabled. `LIVE_TRADING_ENABLED=false` remains a second application-level lock.
