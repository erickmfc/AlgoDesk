"""Deterministic long-only backtest with explicit trading frictions."""
from dataclasses import dataclass
from math import sqrt

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
    trade_slippage = 0.0
    peak_equity = cash
    max_drawdown = 0.0
    fees_total = 0.0
    slippage_total = 0.0
    trades: list[CompletedTrade] = []
    equity_curve: list[float] = []
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
            trade_slippage = abs(fill_price - candle.close) * quantity
            slippage_total += trade_slippage
        elif signal and signal.action == "SELL" and quantity:
            fill_price = candle.close * (1 - config.slippage_bps / 10_000)
            notional = quantity * fill_price
            exit_fee = notional * config.fee_bps / 10_000
            cash += notional - exit_fee
            gross_pnl = (fill_price - entry_price) * quantity
            exit_slippage = abs(candle.close - fill_price) * quantity
            trade_slippage += exit_slippage
            trades.append(CompletedTrade(entry_time, candle.open_time, entry_price, fill_price, quantity, gross_pnl, entry_fee + exit_fee, trade_slippage))
            fees_total += exit_fee
            slippage_total += exit_slippage
            quantity = 0.0
            entry_fee = 0.0
            trade_slippage = 0.0
        equity = cash + (quantity * candle.close)
        equity_curve.append(equity)
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity * 100)
    if quantity and candles:
        final = candles[-1]
        fill_price = final.close * (1 - config.slippage_bps / 10_000)
        notional = quantity * fill_price
        exit_fee = notional * config.fee_bps / 10_000
        cash += notional - exit_fee
        fees_total += exit_fee
        exit_slippage = abs(final.close - fill_price) * quantity
        slippage_total += exit_slippage
        trade_slippage += exit_slippage
        trades.append(CompletedTrade(entry_time, final.open_time, entry_price, fill_price, quantity, (fill_price - entry_price) * quantity, entry_fee + exit_fee, trade_slippage))
    winners = sum(1 for trade in trades if trade.gross_pnl > 0)
    gross_wins = sum(trade.gross_pnl for trade in trades if trade.gross_pnl > 0)
    gross_losses = abs(sum(trade.gross_pnl for trade in trades if trade.gross_pnl < 0))
    net_profit = cash - config.starting_cash
    average_win = gross_wins / winners if winners else 0.0
    losers = len(trades) - winners
    average_loss = gross_losses / losers if losers else 0.0
    expectancy = ((winners / len(trades)) * average_win - (losers / len(trades)) * average_loss) if trades else 0.0
    period_returns = [current / previous - 1 for previous, current in zip(equity_curve, equity_curve[1:]) if previous]
    average_return = sum(period_returns) / len(period_returns) if period_returns else 0.0
    variance = sum((value - average_return) ** 2 for value in period_returns) / len(period_returns) if period_returns else 0.0
    deviation = sqrt(variance)
    downside = [min(value, 0.0) for value in period_returns]
    downside_deviation = sqrt(sum(value * value for value in downside) / len(downside)) if downside else 0.0
    sharpe = (average_return / deviation) * sqrt(365) if deviation else 0.0
    sortino = (average_return / downside_deviation) * sqrt(365) if downside_deviation else 0.0
    periods = max(len(candles) - 1, 1)
    cagr_percent = ((cash / config.starting_cash) ** (365 / periods) - 1) * 100 if cash > 0 else -100.0
    max_drawdown_value = max_drawdown / 100 * max(equity_curve or [config.starting_cash])
    recovery_factor = net_profit / max_drawdown_value if max_drawdown_value else 0.0
    buy_hold_return_percent = ((candles[-1].close / candles[0].close) - 1) * 100 if candles and candles[0].close else 0.0
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
        exposure_percent=config.position_percent if trades else 0,
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
    )
    return result, trades
