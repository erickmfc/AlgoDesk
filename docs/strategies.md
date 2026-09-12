# Estratégia inicial

O primeiro robô é uma implementação pequena e auditável de tendência por
cruzamento de EMA. Ele lê candles fechados, calcula uma EMA rápida e uma EMA
lenta e produz apenas um `Signal`; a estratégia não conhece Binance, banco ou
ordens.

## Configuração

O perfil inicial está em `configs/strategies/ema-btc.yaml`:

- `BTCUSDT`
- `1h`
- EMA rápida `20`
- EMA lenta `50`
- ATR reservado para o próximo estágio de stops e filtro de volatilidade

Os parâmetros são hipóteses de pesquisa, não promessa de retorno. O backtest
real usa somente candles Spot fechados e marca `lookahead: false`.

## Fluxo

```text
candle fechado → EMA Trend → Signal → TradeIntent → RiskEngine
```

O scheduler PAPER já liga esse fluxo a candles fechados da Binance a cada ciclo
de 60 segundos, persistindo sinais, intents, fills simulados, eventos e
snapshots de portfólio. Antes de Testnet ainda faltam splits de validação,
walk-forward, fricções adicionais e soak test.
