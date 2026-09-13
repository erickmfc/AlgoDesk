from math import isfinite

from src.backtest import (
    BacktestConfig,
    run_backtest,
    run_backtest_splits,
    run_parameter_sweep,
    run_walk_forward,
)
from src.strategies import Candle, EmaTrendStrategy, ema


def candles(closes: list[float]) -> list[Candle]:
    return [Candle(index, value, value + 1, value - 1, value) for index, value in enumerate(closes)]


def test_ema_is_deterministic():
    assert ema([10, 12, 14], 2) == [10, 11.333333333333334, 13.11111111111111]


def test_strategy_uses_closed_candle_crossovers():
    signals = EmaTrendStrategy(2, 4).signals(candles([10, 9, 8, 9, 12, 14, 10, 7]))
    assert [signal.action for signal in signals] == ["BUY", "SELL"]


def test_strategy_attaches_configured_atr_exit_levels():
    signals = EmaTrendStrategy(2, 4, atr_period=2, stop_loss_atr=1.0, take_profit_atr=2.0).signals(
        candles([10, 9, 8, 9, 12, 14, 10, 7])
    )

    buy = next(signal for signal in signals if signal.action == "BUY")
    assert buy.stop_price is not None
    assert buy.take_profit_price is not None
    assert buy.stop_price < buy.price < buy.take_profit_price


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


def test_walk_forward_selects_only_from_validation_before_scoring_oos():
    long_candles = candles([100 + ((index // 7) % 2) * 10 + (index % 3) for index in range(300)])
    config = BacktestConfig(fast_period=4, slow_period=8)

    baseline = run_walk_forward(
        long_candles,
        config,
        folds=2,
        candidates=((3, 7), (4, 8), (5, 10)),
    )
    mutated = list(long_candles)
    first_oos_start = baseline["folds"][0]["windows"]["out_of_sample"]["data_start"]
    for index, candle in enumerate(mutated):
        if candle.open_time >= first_oos_start:
            mutated[index] = Candle(
                candle.open_time,
                candle.open,
                candle.high * 5,
                candle.low / 5,
                candle.close * 5,
                candle.volume,
            )
    re_run = run_walk_forward(
        mutated,
        config,
        folds=2,
        candidates=((3, 7), (4, 8), (5, 10)),
    )

    assert baseline["lookahead"] is False
    assert all(fold["lookahead"] is False for fold in baseline["folds"])
    assert baseline["folds"][0]["selected"] == re_run["folds"][0]["selected"]
    assert (
        baseline["folds"][0]["out_of_sample"]["metrics"]
        != re_run["folds"][0]["out_of_sample"]["metrics"]
    )
