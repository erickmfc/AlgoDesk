# AlgoDesk · Architecture Plan

## Guardrails

- Binance Spot only in the first release; no margin, leverage, shorting or withdrawals.
- `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false` are the safe defaults.
- Strategies emit `TradeIntent`; only `RiskEngine` can approve an intent for `OrderManager`.
- API keys stay server-side and are never returned to the dashboard.
- Ambiguous order results are reconciled before any retry.

## Runtime shape

`MarketData → Strategy → TradeIntent → RiskEngine → OrderManager → BrokerAdapter → Binance`

The dashboard is a read-only operator surface. It uses real Binance public
prices through REST/WebSocket and reads worker snapshots/events from
PostgreSQL. The `trader` process owns market cycles, strategy decisions and
execution state; the `api` process serves queries and forwards the operator
hard stop to the worker over the private Compose network.

## Phases

1. Dashboard shell, operator interactions and paper labels (complete)
2. Python domain models, RiskEngine and PaperBroker (complete)
3. Binance Spot public REST/WebSocket adapter and signed account reader (complete)
4. PostgreSQL persistence, user-stream reconciliation and health metrics (complete)
5. Backtest engine with frictions, metrics and independent splits (complete; walk-forward remains)
6. Testnet broker gate and deployment overlays (complete; soak test remains)
7. Live-candidate review; LIVE remains disabled until manually approved

## HD installation

The project root is `E:\AlgoDesk`. Keep `node_modules`, Docker volumes and data paths under `E:\AlgoDesk` or Docker Desktop's HD-backed data root. Never store secrets in Git.
