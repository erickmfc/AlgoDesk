from math import isfinite

from src.backtest import BacktestConfig, run_backtest
from src.strategies import Candle, EmaTrendStrategy, ema


def candles(closes: list[float]) -> list[Candle]:
    return [Candle(index, value, value + 1, value - 1, value) for index, value in enumerate(closes)]


def test_ema_is_deterministic():
    assert ema([10, 12, 14], 2) == [10, 11.333333333333334, 13.11111111111111]


def test_strategy_uses_closed_candle_crossovers():
    signals = EmaTrendStrategy(2, 4).signals(candles([10, 9, 8, 9, 12, 14, 10, 7]))
    assert [signal.action for signal in signals] == ["BUY", "SELL"]


def test_backtest_applies_fees_and_slippage():
    result, trades = run_backtest(candles([10, 9, 8, 9, 12, 14, 10, 7]), BacktestConfig(starting_cash=1000, fee_bps=10, slippage_bps=5, position_percent=50, fast_period=2, slow_period=4))
    assert len(trades) == 1
    assert result.fees > 0
    assert result.slippage > 0
    assert result.equity != 1000
    assert isfinite(result.sharpe)
    assert isfinite(result.sortino)
    assert result.buy_hold_equity > 0
    assert isfinite(result.expectancy)
