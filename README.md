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
- As dependências locais do dashboard, ambiente Python, dados PostgreSQL e configurações versionadas são mantidos em `E:\AlgoDesk`. O painel Docker serve o build Linux da imagem — sem montar os binários Windows de `node_modules` — enquanto o código-fonte e os dados persistentes ficam no HD.
- O adaptador de execução Binance Spot Testnet está implementado, com consulta idempotente por `clientOrderId`, filtros de `exchangeInfo`, reconciliação e User Data Stream. LIVE continua travado por duas chaves (`TRADING_MODE=live` + `LIVE_TRADING_ENABLED=true`) e não deve ser habilitado nesta versão.
- `configs/risk.yaml` e `configs/strategies/ema-btc.yaml` são carregados pelo worker em PAPER/Testnet. O backtest mostra splits independentes, vizinhos de EMA e walk-forward: parâmetros são escolhidos somente na validação, e cada janela OOS só é avaliada após a escolha.
- Futures, Margin, leverage, short e withdrawals não são implementados.

## Docker local/VPS

O mesmo código pode ser executado no HD com PostgreSQL pelo overlay local ou no VPS pelo overlay VPS:

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d --build
```

Para iniciar o Testnet, preencha apenas no `.env` local (que não é versionado)
as credenciais da Binance Spot Testnet e troque o modo:

```dotenv
TRADING_MODE=testnet
BINANCE_TESTNET=true
LIVE_TRADING_ENABLED=false
BINANCE_API_KEY=chave_testnet
BINANCE_API_SECRET=segredo_testnet
ALLOWED_ORIGINS=http://localhost:4173,http://127.0.0.1:4173
```

Depois reinicie com o mesmo comando Docker e confira `/ready`: ele deve mostrar
`mode=testnet` e `account_configured=true`. O worker usa a mesma sequência de
estratégia, risco, idempotência, User Data Stream e reconciliação, mas as ordens
são aceitas somente pelo endpoint Testnet. Não use chaves de produção neste
modo e não altere `LIVE_TRADING_ENABLED` durante esta fase.

Consulte [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md), [TODO.md](TODO.md) e a documentação em `docs/` antes de configurar credenciais Testnet. Nenhuma chave é necessária para o modo PAPER.

No VPS, configure o DNS e suba o mesmo stack com o proxy HTTPS:

```bash
export ALGODESK_DOMAIN=algo.example.com
docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml up -d --build
```

O arquivo `deploy/Caddyfile` encaminha `/api`, `/health`, `/ready` e `/ws`
para o backend e mantém as portas internas do dashboard/API fora da internet.

## Utilitários read-only

Com o stack iniciado, os fluxos operacionais também podem ser executados por
script:

```powershell
python scripts/download_data.py --symbol BTCUSDT --interval 1h --limit 500
python scripts/backtest.py --symbol BTCUSDT --interval 1h --limit 500 --output data/backtest-btc.json
python scripts/paper.py
python scripts/reconcile.py --symbol BTCUSDT
```

O download e o backtest usam somente dados públicos; `paper.py` apenas lê o
estado do worker; `reconcile.py` apenas consulta a conta quando credenciais
server-side estão configuradas.

Para operação e recuperação, consulte [docs/operations.md](docs/operations.md). Os comandos `scripts/diagnose.ps1` e `scripts/backup-postgres.ps1` são os atalhos recomendados para o uso diário.
