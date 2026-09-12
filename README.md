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

O backtest de pesquisa usa candles Spot fechados reais e pode ser consultado
diretamente após subir o serviço:

```powershell
Invoke-RestMethod "http://localhost:8000/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=500"
```

O comando `alembic upgrade head` é executado automaticamente no container do
trader; para executar manualmente no ambiente Python, use `alembic upgrade head`
a partir de `E:\AlgoDesk\apps\trader`.

## Docker

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

## O que é real e o que é PAPER

- Os preços BTCUSDT e ETHUSDT mostrados no painel vêm do endpoint público Spot da Binance, são atualizados a cada 15 segundos e ficam como `—` quando a origem não responde.
- O dashboard tenta primeiro o WebSocket público da Binance e mantém REST como fallback; o indicador mostra a origem efetiva (`WebSocket`, `REST` ou indisponível).
- Equity, PnL, drawdown, posições e activity feed são calculados pelo motor PAPER local a partir de candles fechados reais da Binance, iniciando com capital virtual; não representam saldo, ordens ou histórico da conta Binance. Apenas `BOT-001`/`ema-btc-01` está implantado nesta versão; as outras estações são visuais e aparecem como `NOT DEPLOYED`.
- `/api/account/summary` faz leitura autenticada somente quando as credenciais existem no servidor; sem elas retorna `not configured` e nunca inventa saldo.
- O serviço `api` expõe saúde, risco, ticker público, status de mercado, WebSocket interno, backtest histórico real e o fixture demonstrativo separado; o worker `trader` executa o ciclo PAPER e persiste snapshots. Cotações REST usam `Cache-Control: no-store`.
- O Compose inclui PostgreSQL com volume bindado em `E:\AlgoDesk\data\postgres`; `api` lê snapshots persistidos do worker e encaminha o hard stop por rede interna.
- O adaptador de execução Binance Spot Testnet está implementado, com consulta idempotente por `clientOrderId`, filtros de `exchangeInfo`, reconciliação e User Data Stream. LIVE continua travado por duas chaves (`TRADING_MODE=live` + `LIVE_TRADING_ENABLED=true`) e não deve ser habilitado nesta versão.
- Futures, Margin, leverage, short e withdrawals não são implementados.

## Docker local/VPS

O mesmo código pode ser executado no HD com PostgreSQL pelo overlay local ou no VPS pelo overlay VPS:

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

Consulte [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md), [TODO.md](TODO.md) e a documentação em `docs/` antes de configurar credenciais Testnet. Nenhuma chave é necessária para o modo PAPER.
