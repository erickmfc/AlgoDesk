# Operação diária

O stack local roda a partir de `E:\AlgoDesk` e deve permanecer em `PAPER` até
que as portas de Testnet e de segurança estejam aprovadas. O painel é
`http://localhost:4173/desk`.

## Verificação

```powershell
Set-Location E:\AlgoDesk
.\scripts\diagnose.ps1
```

O diagnóstico consulta somente `/health`, `/ready` e `/api/system/metrics`.
O estado esperado no PC é `mode=paper`, `database_connected=true`,
`live_trading_enabled=false` e `market_data_source=binance-public-spot`.

## Reiniciar e acompanhar

```powershell
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml up -d
docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml logs -f trader api
```

O trabalhador pausa e registra alerta se perder dados, falhar o ciclo ou
detectar divergência de conta. Não apagar o volume `data/postgres` para
resolver uma falha; primeiro preserve os logs e execute o backup.

## Parada de emergência

O botão `PARAR TODOS OS ROBÔS` aciona o hard stop e exige `ENABLE` para
reativação. Em caso de indisponibilidade do painel, o mesmo endpoint pode ser
chamado pelo operador:

```powershell
Invoke-RestMethod http://localhost:8000/api/paper/kill-switch -Method Post `
  -ContentType 'application/json' -Body '{"enabled":true}'
```

Para reativar, somente depois de investigar a causa:

```powershell
Invoke-RestMethod http://localhost:8000/api/paper/kill-switch -Method Post `
  -ContentType 'application/json' -Body '{"enabled":false,"confirmation":"ENABLE"}'
```

## Backup

```powershell
.\scripts\backup-postgres.ps1
```

O dump é gravado em `E:\AlgoDesk\data\backups`. A rotina não envia dados para
fora do computador e não altera o banco em execução.

## Testnet

O Testnet só deve ser iniciado com chaves Spot Testnet no `.env` local,
`TRADING_MODE=testnet` e `LIVE_TRADING_ENABLED=false`. Depois de verificar
`/ready`, execute o soak somente no modo explicitamente escolhido:

```powershell
python scripts/soak_runtime.py --require-mode testnet --cycles 12 --interval 60
```

Sem credenciais, o comando termina como `BLOCKED` e não tenta criar ordens.
Nunca use uma chave de produção no modo Testnet.
