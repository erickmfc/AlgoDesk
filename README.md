# AlgoDesk

Mesa de operações gamificada para pesquisa, backtest e paper trading em Binance Spot. O dashboard consulta o ticker público da Binance através do serviço Python; o motor permanece deliberadamente sem execução live.

## Rodar no HD

```powershell
Set-Location E:\AlgoDesk
npm install
npm run dev
```

Abra `http://localhost:4173`. O modo inicial é `PAPER`. A interface não solicita nem expõe API Secret.

## Docker

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

## O que é real e o que é PAPER

- Os preços BTCUSDT e ETHUSDT mostrados no painel vêm do endpoint público Spot da Binance, são atualizados a cada 15 segundos e ficam como `—` quando a origem não responde.
- Equity, PnL, drawdown, posições, bots e activity feed são um snapshot PAPER local para validar a interface e o motor de risco; não representam saldo, ordens ou histórico da conta Binance.
- O serviço FastAPI expõe saúde, risco e ticker público Spot somente leitura, com `Cache-Control: no-store` para não reaproveitar uma cotação antiga.
- O Compose inclui PostgreSQL com volume bindado em `E:\AlgoDesk\data\postgres`.
- LIVE, Futures, Margin, leverage, short e withdrawals não são implementados.

## Próxima fase

Implementar PaperBroker, RiskEngine e o adaptador oficial de market data da Binance, sempre com testes mockados e reconciliação antes de qualquer ordem externa. Consulte [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) e [TODO.md](TODO.md).
