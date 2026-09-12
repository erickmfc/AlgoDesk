# AlgoDesk · Architecture Plan

## Guardrails

- Binance Spot only in the first release; no margin, leverage, shorting or withdrawals.
- `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false` are the safe defaults.
- Strategies emit `TradeIntent`; only `RiskEngine` can approve an intent for `OrderManager`.
- API keys stay server-side and are never returned to the dashboard.
- Ambiguous order results are reconciled before any retry.

## Runtime shape

`MarketData → Strategy → TradeIntent → RiskEngine → ExecutionManager → BrokerAdapter → Binance`

The dashboard is a read-only operator surface in v0.1. It currently uses a deterministic demo snapshot so the visual workflow can be reviewed without credentials. The Python service is the seam for real market data and paper execution.

## Phases

1. Dashboard shell and operator interactions (current)
2. Python domain models, RiskEngine and PaperBroker
3. Binance Spot market adapter with REST/WebSocket reconnection
4. PostgreSQL persistence, reconciliation and health metrics
5. Backtest engine with fees, slippage and walk-forward splits
6. Testnet gate and deployment overlays
7. Live-candidate review; LIVE remains disabled until manually approved

## HD installation

The project root is `E:\AlgoDesk`. Keep `node_modules`, Docker volumes and data paths under `E:\AlgoDesk` or Docker Desktop's HD-backed data root. Never store secrets in Git.
