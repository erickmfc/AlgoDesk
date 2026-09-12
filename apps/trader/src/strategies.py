"""Closed-candle strategy primitives for research and paper execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Signal:
    timestamp: int
    action: str
    price: float
    reason: str


def ema(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * alpha) + (result[-1] * (1 - alpha)))
    return result


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not candles:
        return []
    true_ranges: list[float] = []
    for index, candle in enumerate(candles):
        previous_close = candles[index - 1].close if index else candle.close
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
    return ema(true_ranges, period)


class EmaTrendStrategy:
    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        if fast_period >= slow_period:
            raise ValueError("fast EMA must be smaller than slow EMA")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def signals(self, candles: list[Candle]) -> list[Signal]:
        closes = [candle.close for candle in candles]
        fast = ema(closes, self.fast_period)
        slow = ema(closes, self.slow_period)
        signals: list[Signal] = []
        # Do not trade on the synthetic EMA seed; wait for a full slow window.
        for index in range(max(1, self.slow_period), len(candles)):
            crossed_up = fast[index] > slow[index] and fast[index - 1] <= slow[index - 1]
            crossed_down = fast[index] < slow[index] and fast[index - 1] >= slow[index - 1]
            if crossed_up:
                signals.append(
                    Signal(
                        candles[index].open_time,
                        "BUY",
                        candles[index].close,
                        "fast EMA crossed above slow EMA",
                    )
                )
            elif crossed_down:
                signals.append(
                    Signal(
                        candles[index].open_time,
                        "SELL",
                        candles[index].close,
                        "fast EMA crossed below slow EMA",
                    )
                )
        return signals
