# Backtesting

The primary research endpoint is:

```text
/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=500
```

It downloads public Binance Spot klines, removes the still-open candle,
persists the closed candles with the exchange/symbol/interval/open-time unique
key and runs the EMA crossover with fees, slippage, spread, one-bar latency,
position sizing, exchange filters and timeframe-aware annualisation. Optional
ATR stop/take-profit and partial-fill parameters are part of the research
engine. The result includes return, net profit, CAGR, Sharpe, Sortino,
drawdown, profit factor, expectancy, win rate, average win, average loss,
friction totals, exposure, maximum exposure and a buy-and-hold comparison.
The response explicitly reports `lookahead: false` and the date range used.

The endpoint also returns independent `in_sample`, `validation` and
`out_of_sample` summaries. The five neighboring EMA candidates are evaluated
on the in-sample segment only. Its `walk_forward` result creates chronological
folds, ranks candidate parameters only with the validation window, and scores
the selected parameter on an untouched out-of-sample window. The response
records the exact data ranges and `lookahead: false` for every fold.

`/api/backtests/demo` remains only as a deterministic unit-test fixture. Its
synthetic candles are not market history and must never be used as evidence of
profitability. A supervised Testnet soak remains required before any
live-candidate review.
