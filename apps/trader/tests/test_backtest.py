from math import isfinite

from src.backtest import BacktestConfig, run_backtest, run_backtest_splits, run_parameter_sweep
from src.strategies import Candle, EmaTrendStrategy, ema


def candles(closes: list[float]) -> list[Candle]:
    return [Candle(index, value, value + 1, value - 1, value) for index, value in enumerate(closes)]


def test_ema_is_deterministic():
    assert ema([10, 12, 14], 2) == [10, 11.333333333333334, 13.11111111111111]


def test_strategy_uses_closed_candle_crossovers():
    signals = EmaTrendStrategy(2, 4).signals(candles([10, 9, 8, 9, 12, 14, 10, 7]))
    assert [signal.action for signal in signals] == ["BUY", "SELL"]


def test_backtest_applies_fees_and_slippage():
    result, trades = run_backtest(
        candles([10, 9, 8, 9, 12, 14, 10, 7]),
        BacktestConfig(
            starting_cash=1000,
            fee_bps=10,
            slippage_bps=5,
            position_percent=50,
            fast_period=2,
            slow_period=4,
        ),
    )
    assert len(trades) == 1
    assert result.fees > 0
    assert result.slippage > 0
    assert result.equity != 1000
    assert isfinite(result.sharpe)
    assert isfinite(result.sortino)
    assert result.buy_hold_equity > 0
    assert isfinite(result.expectancy)


def test_backtest_reports_spread_latency_and_partial_fill_friction():
    result, _ = run_backtest(
        candles([10, 9, 8, 9, 12, 14, 10, 7]),
        BacktestConfig(
            starting_cash=1000,
            spread_bps=4,
            latency_bars=1,
            partial_fill_ratio=0.5,
            position_percent=50,
            fast_period=2,
            slow_period=4,
        ),
    )

    assert result.spread > 0
    assert result.latency_bars == 1
    assert result.partial_fills > 0


def test_backtest_splits_and_neighbor_sweep_are_explicit():
    long_candles = candles([100 + ((index // 7) % 2) * 10 + (index % 3) for index in range(180)])
    config = BacktestConfig(fast_period=4, slow_period=8)

    splits = run_backtest_splits(long_candles, config)
    sweep = run_parameter_sweep(long_candles, config)

    assert [item["name"] for item in splits] == ["in_sample", "validation", "out_of_sample"]
    assert all(item["lookahead"] is False for item in splits)
    assert len(sweep) == 5
