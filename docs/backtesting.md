# Backtesting

The primary research endpoint is:

```text
/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=500
```

It downloads public Binance Spot klines, removes the still-open candle,
persists the closed candles with the exchange/symbol/interval/open-time unique
key and runs the EMA crossover with fees, slippage, position sizing and
timeframe-aware annualisation. The result includes return, net profit, CAGR,
Sharpe, Sortino, drawdown, profit factor, expectancy, win rate, average win,
average loss, fees, slippage, exposure and a buy-and-hold comparison. The
response explicitly reports `lookahead: false` and the date range used.

`/api/backtests/demo` remains only as a deterministic unit-test fixture. Its
synthetic candles are not market history and must never be used as evidence of
profitability. In-sample/validation/out-of-sample splits and walk-forward
analysis are still required before a Testnet gate.
