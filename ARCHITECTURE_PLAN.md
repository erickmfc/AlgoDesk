# AlgoDesk · Architecture Plan

## Guardrails

- Binance Spot only in the first release; no margin, leverage, shorting or withdrawals.
- `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false` are the safe defaults.
- Strategies emit `TradeIntent`; only `RiskEngine` can approve an intent for `OrderManager`.
- API keys stay server-side and are never returned to the dashboard.
- Ambiguous order results are reconciled before any retry.

## Runtime shape

`MarketData → Strategy → TradeIntent → RiskEngine → ExecutionManager → BrokerAdapter → Binance`

The dashboard is a read-only operator surface. It uses a deterministic PAPER
snapshot for bot/account metrics and real Binance public market prices through
REST/WebSocket. An optional server-side signed account reader is available but
does not submit orders. The Python service is the seam for real market data and
paper execution.

## Phases

1. Dashboard shell, operator interactions and paper labels (complete)
2. Python domain models, RiskEngine and PaperBroker (complete)
3. Binance Spot public REST/WebSocket adapter and signed account reader (partial)
4. PostgreSQL persistence, user-stream reconciliation and health metrics
5. Backtest engine with frictions, metrics and walk-forward splits (partial)
6. Testnet gate and deployment overlays
7. Live-candidate review; LIVE remains disabled until manually approved

## HD installation

The project root is `E:\AlgoDesk`. Keep `node_modules`, Docker volumes and data paths under `E:\AlgoDesk` or Docker Desktop's HD-backed data root. Never store secrets in Git.
