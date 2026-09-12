"""Deterministic long-only backtest with explicit trading frictions."""
from dataclasses import dataclass

from .strategies import Candle, EmaTrendStrategy


@dataclass(frozen=True)
class BacktestConfig:
    starting_cash: float = 10_000.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    position_percent: float = 10.0
    fast_period: int = 20
    slow_period: int = 50


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
    exposure_percent: float


def run_backtest(candles: list[Candle], config: BacktestConfig | None = None) -> tuple[BacktestResult, list[CompletedTrade]]:
    config = config or BacktestConfig()
    if config.starting_cash <= 0 or not 0 < config.position_percent <= 100:
        raise ValueError("starting_cash and position_percent must be valid")
    signals = {signal.timestamp: signal for signal in EmaTrendStrategy(config.fast_period, config.slow_period).signals(candles)}
    cash = config.starting_cash
    quantity = 0.0
    entry_time = 0
    entry_price = 0.0
    entry_fee = 0.0
    peak_equity = cash
    max_drawdown = 0.0
    fees_total = 0.0
    slippage_total = 0.0
    trades: list[CompletedTrade] = []
    for candle in candles:
        signal = signals.get(candle.open_time)
        if signal and signal.action == "BUY" and quantity == 0:
            notional = cash * config.position_percent / 100
            fill_price = candle.close * (1 + config.slippage_bps / 10_000)
            quantity = notional / fill_price
            entry_fee = notional * config.fee_bps / 10_000
            cash -= notional + entry_fee
            entry_time, entry_price = candle.open_time, fill_price
            fees_total += entry_fee
            slippage_total += abs(fill_price - candle.close) * quantity
        elif signal and signal.action == "SELL" and quantity:
            fill_price = candle.close * (1 - config.slippage_bps / 10_000)
            notional = quantity * fill_price
            exit_fee = notional * config.fee_bps / 10_000
            cash += notional - exit_fee
            gross_pnl = (fill_price - entry_price) * quantity
            trades.append(CompletedTrade(entry_time, candle.open_time, entry_price, fill_price, quantity, gross_pnl, entry_fee + exit_fee, slippage_total))
            fees_total += exit_fee
            slippage_total += abs(candle.close - fill_price) * quantity
            quantity = 0.0
            entry_fee = 0.0
        equity = cash + (quantity * candle.close)
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity * 100)
    if quantity and candles:
        final = candles[-1]
        fill_price = final.close * (1 - config.slippage_bps / 10_000)
        notional = quantity * fill_price
        exit_fee = notional * config.fee_bps / 10_000
        cash += notional - exit_fee
        fees_total += exit_fee
        slippage_total += abs(final.close - fill_price) * quantity
        trades.append(CompletedTrade(entry_time, final.open_time, entry_price, fill_price, quantity, (fill_price - entry_price) * quantity, entry_fee + exit_fee, slippage_total))
    winners = sum(1 for trade in trades if trade.gross_pnl > 0)
    gross_wins = sum(trade.gross_pnl for trade in trades if trade.gross_pnl > 0)
    gross_losses = abs(sum(trade.gross_pnl for trade in trades if trade.gross_pnl < 0))
    result = BacktestResult(
        equity=cash,
        return_percent=(cash / config.starting_cash - 1) * 100,
        max_drawdown_percent=max_drawdown,
        win_rate_percent=(winners / len(trades) * 100) if trades else 0,
        profit_factor=(gross_wins / gross_losses) if gross_losses else (None if gross_wins else 0),
        trades=len(trades),
        fees=fees_total,
        slippage=slippage_total,
        exposure_percent=config.position_percent if trades else 0,
    )
    return result, trades
