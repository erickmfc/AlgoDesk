"""Deterministic, long-only backtesting with explicit market frictions.

The engine is intentionally small and auditable. It only consumes closed
candles and never calls an exchange or an order endpoint.
"""

from dataclasses import dataclass
from math import sqrt
from typing import cast

from .strategies import Candle, EmaTrendStrategy, Signal, atr


@dataclass(frozen=True)
class BacktestConfig:
    starting_cash: float = 10_000.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    spread_bps: float = 0.0
    latency_bars: int = 0
    partial_fill_ratio: float = 1.0
    position_percent: float = 10.0
    fast_period: int = 20
    slow_period: int = 50
    atr_period: int = 14
    stop_loss_atr: float = 0.0
    take_profit_atr: float = 0.0
    min_quantity: float = 0.0
    min_notional: float = 0.0
    tick_size: float = 0.0
    step_size: float = 0.0
    periods_per_year: float = 365.0


@dataclass(frozen=True)
class CompletedTrade:
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    slippage: float
    net_pnl: float = 0.0
    exit_reason: str = "signal"


@dataclass(frozen=True)
class BacktestResult:
    equity: float
    return_percent: float
    max_drawdown_percent: float
    win_rate_percent: float
    profit_factor: float | None
    trades: int
    fees: float
    slippage: float
    spread: float
    exposure_percent: float
    max_exposure_percent: float
    net_profit: float
    cagr_percent: float
    sharpe: float
    sortino: float
    average_win: float
    average_loss: float
    expectancy: float
    recovery_factor: float
    buy_hold_return_percent: float
    buy_hold_equity: float
    partial_fills: int
    stop_loss_trades: int
    take_profit_trades: int
    latency_bars: int


DEFAULT_EMA_CANDIDATES: tuple[tuple[int, int], ...] = (
    (18, 45),
    (19, 48),
    (20, 50),
    (21, 52),
    (22, 55),
)


def _validate_config(config: BacktestConfig) -> None:
    if (
        config.starting_cash <= 0
        or not 0 < config.position_percent <= 100
        or config.periods_per_year <= 0
        or config.fee_bps < 0
        or config.slippage_bps < 0
        or config.spread_bps < 0
        or config.latency_bars < 0
        or not 0 < config.partial_fill_ratio <= 1
        or config.fast_period <= 0
        or config.slow_period <= config.fast_period
        or config.atr_period <= 0
        or config.stop_loss_atr < 0
        or config.take_profit_atr < 0
        or config.min_quantity < 0
        or config.min_notional < 0
        or config.tick_size < 0
        or config.step_size < 0
    ):
        raise ValueError("invalid backtest configuration")


def _floor_increment(value: float, increment: float) -> float:
    if increment <= 0:
        return value
    return int(value / increment) * increment


def _fill_price(raw_price: float, side: str, config: BacktestConfig) -> tuple[float, float, float]:
    spread_component = config.spread_bps / 20_000
    slippage_component = config.slippage_bps / 10_000
    direction = 1 if side == "BUY" else -1
    with_spread = raw_price * (1 + direction * spread_component)
    filled = raw_price * (1 + direction * (spread_component + slippage_component))
    slippage_cost = abs(filled - with_spread)
    spread_cost = abs(with_spread - raw_price)
    return filled, slippage_cost, spread_cost


def run_backtest(
    candles: list[Candle], config: BacktestConfig | None = None
) -> tuple[BacktestResult, list[CompletedTrade]]:
    config = config or BacktestConfig()
    _validate_config(config)
    if not candles:
        raise ValueError("at least one candle is required")

    strategy_signals = EmaTrendStrategy(config.fast_period, config.slow_period).signals(candles)
    candle_indexes = {candle.open_time: index for index, candle in enumerate(candles)}
    scheduled_signals: dict[int, Signal] = {}
    for signal in strategy_signals:
        source_index = candle_indexes.get(signal.timestamp)
        if source_index is None:
            continue
        execution_index = source_index + config.latency_bars
        if execution_index < len(candles):
            scheduled_signals[execution_index] = signal

    atr_values = atr(candles, config.atr_period)
    cash = config.starting_cash
    quantity = 0.0
    entry_time = 0
    entry_price = 0.0
    entry_fee_per_unit = 0.0
    entry_slippage_per_unit = 0.0
    stop_price: float | None = None
    take_profit_price: float | None = None
    peak_equity = cash
    max_drawdown = 0.0
    fees_total = 0.0
    slippage_total = 0.0
    spread_total = 0.0
    trades: list[CompletedTrade] = []
    equity_curve: list[float] = []
    invested_bars = 0
    max_exposure = 0.0
    partial_fills = 0
    stop_loss_trades = 0
    take_profit_trades = 0

    def close_position(index: int, raw_price: float, reason: str) -> None:
        nonlocal cash, quantity, entry_time, entry_price
        nonlocal entry_fee_per_unit, entry_slippage_per_unit, stop_price, take_profit_price
        nonlocal fees_total, slippage_total, spread_total, stop_loss_trades, take_profit_trades
        if quantity <= 0:
            return
        fill_price, slippage_per_unit, spread_per_unit = _fill_price(raw_price, "SELL", config)
        filled_quantity = quantity * config.partial_fill_ratio
        if config.partial_fill_ratio >= 1:
            filled_quantity = quantity
        filled_quantity = max(0.0, min(quantity, filled_quantity))
        if filled_quantity <= 0:
            return
        notional = filled_quantity * fill_price
        exit_fee = notional * config.fee_bps / 10_000
        allocated_entry_fee = entry_fee_per_unit * filled_quantity
        allocated_entry_slippage = entry_slippage_per_unit * filled_quantity
        gross_pnl = (fill_price - entry_price) * filled_quantity
        total_fees = allocated_entry_fee + exit_fee
        total_slippage = allocated_entry_slippage + slippage_per_unit * filled_quantity
        net_pnl = gross_pnl - total_fees
        cash += notional - exit_fee
        fees_total += exit_fee
        slippage_total += slippage_per_unit * filled_quantity
        spread_total += spread_per_unit * filled_quantity
        trades.append(
            CompletedTrade(
                entry_time,
                candles[index].open_time,
                entry_price,
                fill_price,
                filled_quantity,
                gross_pnl,
                total_fees,
                total_slippage,
                net_pnl,
                reason,
            )
        )
        quantity -= filled_quantity
        if reason == "stop_loss":
            stop_loss_trades += 1
        elif reason == "take_profit":
            take_profit_trades += 1
        if quantity <= 1e-12:
            quantity = 0.0
            entry_time = 0
            entry_price = 0.0
            entry_fee_per_unit = 0.0
            entry_slippage_per_unit = 0.0
            stop_price = None
            take_profit_price = None

    for index, candle in enumerate(candles):
        if quantity > 0:
            # If both levels are touched by one bar, assume the stop happened
            # first. This conservative rule avoids optimistic fills.
            if stop_price is not None and candle.low <= stop_price:
                close_position(index, stop_price, "stop_loss")
            elif take_profit_price is not None and candle.high >= take_profit_price:
                close_position(index, take_profit_price, "take_profit")

        scheduled_signal = scheduled_signals.get(index)
        if scheduled_signal and scheduled_signal.action == "BUY" and quantity == 0:
            raw_price = candle.close if config.latency_bars == 0 else candle.open
            fill_price, slippage_per_unit, spread_per_unit = _fill_price(raw_price, "BUY", config)
            requested_quantity = (cash * config.position_percent / 100) / fill_price
            requested_quantity = _floor_increment(requested_quantity, config.step_size)
            if config.min_quantity and requested_quantity < config.min_quantity:
                requested_quantity = 0.0
            if config.min_notional and requested_quantity * fill_price < config.min_notional:
                requested_quantity = 0.0
            if requested_quantity > 0:
                fill_quantity = requested_quantity * config.partial_fill_ratio
                if config.partial_fill_ratio >= 1:
                    fill_quantity = requested_quantity
                fill_quantity = _floor_increment(fill_quantity, config.step_size)
                notional = fill_quantity * fill_price
                if fill_quantity > 0 and (
                    not config.min_notional or notional >= config.min_notional
                ):
                    entry_fee = notional * config.fee_bps / 10_000
                    cash -= notional + entry_fee
                    quantity = fill_quantity
                    entry_time = scheduled_signal.timestamp
                    entry_price = fill_price
                    entry_fee_per_unit = entry_fee / fill_quantity
                    entry_slippage_per_unit = slippage_per_unit
                    fees_total += entry_fee
                    slippage_total += slippage_per_unit * fill_quantity
                    spread_total += spread_per_unit * fill_quantity
                    if config.partial_fill_ratio < 1:
                        partial_fills += 1
                    volatility = atr_values[index] if index < len(atr_values) else 0.0
                    stop_price = (
                        fill_price - volatility * config.stop_loss_atr
                        if config.stop_loss_atr and volatility > 0
                        else None
                    )
                    take_profit_price = (
                        fill_price + volatility * config.take_profit_atr
                        if config.take_profit_atr and volatility > 0
                        else None
                    )
        elif scheduled_signal and scheduled_signal.action == "SELL" and quantity > 0:
            raw_price = candle.close if config.latency_bars == 0 else candle.open
            close_position(index, raw_price, "signal")
            if config.partial_fill_ratio < 1 and quantity > 0:
                partial_fills += 1

        equity = cash + quantity * candle.close
        equity_curve.append(equity)
        if quantity > 0:
            invested_bars += 1
            exposure = quantity * candle.close / equity * 100 if equity else 0.0
            max_exposure = max(max_exposure, exposure)
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity * 100)

    if quantity:
        close_position(len(candles) - 1, candles[-1].close, "end_of_data")
        equity_curve[-1] = cash

    winners = sum(1 for trade in trades if trade.net_pnl > 0)
    gross_wins = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    gross_losses = abs(sum(trade.net_pnl for trade in trades if trade.net_pnl < 0))
    net_profit = cash - config.starting_cash
    average_win = gross_wins / winners if winners else 0.0
    losers = len(trades) - winners
    average_loss = gross_losses / losers if losers else 0.0
    expectancy = (
        ((winners / len(trades)) * average_win - (losers / len(trades)) * average_loss)
        if trades
        else 0.0
    )
    period_returns = [
        current / previous - 1
        for previous, current in zip(equity_curve, equity_curve[1:])
        if previous
    ]
    average_return = sum(period_returns) / len(period_returns) if period_returns else 0.0
    variance = (
        sum((value - average_return) ** 2 for value in period_returns) / len(period_returns)
        if period_returns
        else 0.0
    )
    deviation = sqrt(variance)
    downside = [min(value, 0.0) for value in period_returns]
    downside_deviation = (
        sqrt(sum(value * value for value in downside) / len(downside)) if downside else 0.0
    )
    sharpe = (average_return / deviation) * sqrt(config.periods_per_year) if deviation else 0.0
    sortino = (
        (average_return / downside_deviation) * sqrt(config.periods_per_year)
        if downside_deviation
        else 0.0
    )
    periods = max(len(candles) - 1, 1)
    cagr_percent = (
        ((cash / config.starting_cash) ** (config.periods_per_year / periods) - 1) * 100
        if cash > 0
        else -100.0
    )
    max_drawdown_value = max_drawdown / 100 * max(equity_curve or [config.starting_cash])
    recovery_factor = net_profit / max_drawdown_value if max_drawdown_value else 0.0
    buy_hold_return_percent = (
        ((candles[-1].close / candles[0].close) - 1) * 100 if candles[0].close else 0.0
    )
    buy_hold_equity = config.starting_cash * (1 + buy_hold_return_percent / 100)
    result = BacktestResult(
        equity=cash,
        return_percent=(cash / config.starting_cash - 1) * 100,
        max_drawdown_percent=max_drawdown,
        win_rate_percent=(winners / len(trades) * 100) if trades else 0,
        profit_factor=(gross_wins / gross_losses) if gross_losses else (None if gross_wins else 0),
        trades=len(trades),
        fees=fees_total,
        slippage=slippage_total,
        spread=spread_total,
        exposure_percent=(invested_bars / len(candles) * 100) if candles else 0.0,
        max_exposure_percent=max_exposure,
        net_profit=net_profit,
        cagr_percent=cagr_percent,
        sharpe=sharpe,
        sortino=sortino,
        average_win=average_win,
        average_loss=average_loss,
        expectancy=expectancy,
        recovery_factor=recovery_factor,
        buy_hold_return_percent=buy_hold_return_percent,
        buy_hold_equity=buy_hold_equity,
        partial_fills=partial_fills,
        stop_loss_trades=stop_loss_trades,
        take_profit_trades=take_profit_trades,
        latency_bars=config.latency_bars,
    )
    return result, trades


def run_backtest_splits(
    candles: list[Candle],
    config: BacktestConfig | None = None,
    *,
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
) -> list[dict[str, object]]:
    """Run independent in-sample, validation and out-of-sample partitions."""
    config = config or BacktestConfig()
    if (
        not 0 < train_ratio < 1
        or not 0 <= validation_ratio < 1
        or train_ratio + validation_ratio >= 1
    ):
        raise ValueError("split ratios must leave a positive out-of-sample segment")
    if len(candles) <= config.slow_period * 3:
        return []
    train_end = max(config.slow_period + 1, int(len(candles) * train_ratio))
    validation_end = max(
        train_end + config.slow_period + 1,
        int(len(candles) * (train_ratio + validation_ratio)),
    )
    validation_end = min(validation_end, len(candles) - config.slow_period - 1)
    segments = (
        ("in_sample", candles[:train_end]),
        ("validation", candles[train_end:validation_end]),
        ("out_of_sample", candles[validation_end:]),
    )
    results: list[dict[str, object]] = []
    for name, segment in segments:
        if len(segment) <= config.slow_period:
            continue
        result, trades = run_backtest(segment, config)
        results.append(
            {
                "name": name,
                "data_points": len(segment),
                "data_start": segment[0].open_time,
                "data_end": segment[-1].open_time,
                "metrics": result.__dict__,
                "trades": len(trades),
                "lookahead": False,
            }
        )
    return results


def run_parameter_sweep(
    candles: list[Candle], config: BacktestConfig | None = None
) -> list[dict[str, object]]:
    """Evaluate neighboring EMA hypotheses on the in-sample segment only."""
    config = config or BacktestConfig()
    if not candles:
        return []
    train_end = max(config.slow_period + 1, int(len(candles) * 0.6))
    research_candles = candles[: min(train_end, len(candles))]
    results: list[dict[str, object]] = []
    for fast_period, slow_period in DEFAULT_EMA_CANDIDATES:
        candidate = BacktestConfig(
            **{**config.__dict__, "fast_period": fast_period, "slow_period": slow_period}
        )
        result, _ = run_backtest(research_candles, candidate)
        results.append(
            {
                "fast_period": fast_period,
                "slow_period": slow_period,
                "data_points": len(research_candles),
                "evaluation_scope": "in_sample",
                "metrics": result.__dict__,
            }
        )
    return results


def _selection_score(result: BacktestResult) -> tuple[float, float, float, int]:
    """Rank a candidate using validation data only, conservatively."""
    return (
        result.expectancy,
        result.return_percent,
        -result.max_drawdown_percent,
        result.trades,
    )


def run_walk_forward(
    candles: list[Candle],
    config: BacktestConfig | None = None,
    *,
    folds: int = 3,
    initial_train_ratio: float = 0.5,
    validation_ratio: float = 0.2,
    candidates: tuple[tuple[int, int], ...] = DEFAULT_EMA_CANDIDATES,
) -> dict[str, object]:
    """Select EMA parameters on validation windows, then score untouched OOS windows.

    Each fold is chronological.  A fold's test candles are never evaluated until
    after its candidate is selected; later folds may use earlier OOS periods as
    historical data, as they would in a real rolling deployment.
    """
    config = config or BacktestConfig()
    _validate_config(config)
    if (
        folds <= 0
        or not 0 < initial_train_ratio < 1
        or not 0 < validation_ratio < 1
        or initial_train_ratio + validation_ratio >= 1
        or not candidates
    ):
        raise ValueError("invalid walk-forward configuration")

    minimum_segment = config.slow_period + 1
    initial_train_size = max(minimum_segment, int(len(candles) * initial_train_ratio))
    validation_size = max(minimum_segment, int(len(candles) * validation_ratio))
    first_test_start = initial_train_size + validation_size
    remaining = len(candles) - first_test_start
    actual_folds = min(folds, remaining // minimum_segment)
    if actual_folds <= 0:
        return {
            "lookahead": False,
            "selection_metric": "validation_expectancy_then_return_then_drawdown",
            "folds": [],
            "message": "not enough candles for independent train, validation and OOS windows",
        }

    test_size = remaining // actual_folds
    results: list[dict[str, object]] = []
    for fold in range(actual_folds):
        test_start = first_test_start + fold * test_size
        test_end = len(candles) if fold == actual_folds - 1 else test_start + test_size
        validation_start = test_start - validation_size
        training = candles[:validation_start]
        validation = candles[validation_start:test_start]
        out_of_sample = candles[test_start:test_end]
        evaluations: list[dict[str, object]] = []
        for fast_period, slow_period in candidates:
            candidate = BacktestConfig(
                **{**config.__dict__, "fast_period": fast_period, "slow_period": slow_period}
            )
            train_metrics, _ = run_backtest(training, candidate)
            validation_metrics, _ = run_backtest(validation, candidate)
            evaluations.append(
                {
                    "fast_period": fast_period,
                    "slow_period": slow_period,
                    "in_sample": train_metrics,
                    "validation": validation_metrics,
                }
            )
        selected = max(
            evaluations,
            key=lambda item: _selection_score(item["validation"]),  # type: ignore[arg-type]
        )
        selected_config = BacktestConfig(
            **{
                **config.__dict__,
                "fast_period": cast(int, selected["fast_period"]),
                "slow_period": cast(int, selected["slow_period"]),
            }
        )
        oos_metrics, oos_trades = run_backtest(out_of_sample, selected_config)
        results.append(
            {
                "fold": fold + 1,
                "lookahead": False,
                "windows": {
                    "in_sample": {
                        "data_points": len(training),
                        "data_start": training[0].open_time,
                        "data_end": training[-1].open_time,
                    },
                    "validation": {
                        "data_points": len(validation),
                        "data_start": validation[0].open_time,
                        "data_end": validation[-1].open_time,
                    },
                    "out_of_sample": {
                        "data_points": len(out_of_sample),
                        "data_start": out_of_sample[0].open_time,
                        "data_end": out_of_sample[-1].open_time,
                    },
                },
                "candidate_evaluations": [
                    {
                        "fast_period": item["fast_period"],
                        "slow_period": item["slow_period"],
                        "in_sample": item["in_sample"].__dict__,  # type: ignore[union-attr]
                        "validation": item["validation"].__dict__,  # type: ignore[union-attr]
                    }
                    for item in evaluations
                ],
                "selected": {
                    "fast_period": selected["fast_period"],
                    "slow_period": selected["slow_period"],
                    "selection_scope": "validation_only",
                    "validation_metrics": selected["validation"].__dict__,  # type: ignore[union-attr]
                },
                "out_of_sample": {
                    "metrics": oos_metrics.__dict__,
                    "trades": len(oos_trades),
                    "selection_scope": "untouched_until_scoring",
                },
            }
        )
    return {
        "lookahead": False,
        "selection_metric": "validation_expectancy_then_return_then_drawdown",
        "folds": results,
    }
