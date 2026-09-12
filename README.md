# AlgoDesk

Mesa de operações gamificada para pesquisa, backtest e paper trading em Binance Spot. O dashboard já está navegável e consulta preços públicos da Binance através do serviço Python; o motor permanece sem execução live.

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

## Limites atuais

- O dashboard usa snapshot demonstrativo para a primeira entrega visual e já pode consumir o ticker público Spot.
- O serviço FastAPI expõe saúde, risco e ticker público Spot somente leitura.
- O Compose inclui PostgreSQL com volume bindado em `E:\AlgoDesk\data\postgres`.
- LIVE, Futures, Margin, leverage, short e withdrawals não são implementados.

## Próxima fase

Implementar PaperBroker, RiskEngine e o adaptador oficial de market data da Binance, sempre com testes mockados e reconciliação antes de qualquer ordem externa. Consulte [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) e [TODO.md](TODO.md).
