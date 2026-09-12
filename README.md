# AlgoDesk

Mesa de operações gamificada para pesquisa, backtest e paper trading em Binance Spot. O dashboard consulta o ticker público da Binance através do serviço Python; o motor permanece deliberadamente sem execução live.

## Rodar no HD

```powershell
Set-Location E:\AlgoDesk
npm install
& .\.venv\Scripts\python.exe -m uvicorn src.main:app --app-dir apps\trader --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
Set-Location E:\AlgoDesk
npm run dev
```

Abra `http://localhost:4173`. O modo inicial é `PAPER`. A interface não solicita nem expõe API Secret. O SQLite de desenvolvimento fica em `E:\AlgoDesk\data\algodesk.db`.

## Docker

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

## O que é real e o que é PAPER

- Os preços BTCUSDT e ETHUSDT mostrados no painel vêm do endpoint público Spot da Binance, são atualizados a cada 15 segundos e ficam como `—` quando a origem não responde.
- O dashboard tenta primeiro o WebSocket público da Binance e mantém REST como fallback; o indicador mostra a origem efetiva (`WebSocket`, `REST` ou indisponível).
- Equity, PnL, drawdown, posições, bots e activity feed são um snapshot PAPER local para validar a interface e o motor de risco; não representam saldo, ordens ou histórico da conta Binance.
- `/api/account/summary` faz leitura autenticada somente quando as credenciais existem no servidor; sem elas retorna `not configured` e nunca inventa saldo.
- O serviço FastAPI expõe saúde, risco, ticker público, status de mercado, WebSocket interno e backtest demonstrativo; cotações REST usam `Cache-Control: no-store`.
- O Compose inclui PostgreSQL com volume bindado em `E:\AlgoDesk\data\postgres`.
- LIVE, Futures, Margin, leverage, short e withdrawals não são implementados.

## Docker local/VPS

O mesmo código pode ser executado no HD com PostgreSQL pelo overlay local ou no VPS pelo overlay VPS:

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

Consulte [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md), [TODO.md](TODO.md) e a documentação em `docs/` para as portas restantes antes de qualquer Testnet/LIVE.
