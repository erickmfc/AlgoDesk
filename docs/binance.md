# Binance integration boundary

The first external integration is Binance Spot market data. The adapter must use official REST and WebSocket interfaces, read current `exchangeInfo` filters at runtime, back off on rate limits, reconnect user streams, and reconcile after reconnects.

No secret belongs in the frontend, Git or logs. The intended key permissions are read and Spot Trading only, with withdrawals, Futures and Margin disabled. `LIVE_TRADING_ENABLED=false` remains a second application-level lock.
