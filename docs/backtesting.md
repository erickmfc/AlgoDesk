# Backtesting

The deterministic research endpoint is `/api/backtests/demo`. It uses closed
candles and an EMA crossover with configurable fee, slippage, position size and
EMA windows. The result includes return, net profit, CAGR approximation,
Sharpe, Sortino, drawdown, profit factor, expectancy, win rate, average win,
average loss, fees, slippage, exposure and a buy-and-hold comparison.

The demo candles are synthetic and must not be interpreted as market history or
as evidence of profitability. Historical ingestion, in-sample/validation/
out-of-sample splits and walk-forward analysis are still required before a
Testnet gate.
