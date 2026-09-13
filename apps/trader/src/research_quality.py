"""Validation helpers for historical Binance candle research."""

from dataclasses import dataclass

from .strategies import Candle


@dataclass(frozen=True)
class CandleQuality:
    candles: int
    duplicates: int
    invalid_ohlc: int
    negative_volume: int
    non_monotonic: int
    gaps: int

    @property
    def valid(self) -> bool:
        return not any(
            (self.duplicates, self.invalid_ohlc, self.negative_volume, self.non_monotonic)
        )


def inspect_candles(candles: list[Candle], expected_interval_ms: int) -> CandleQuality:
    timestamps = [c.open_time for c in candles]
    duplicates = len(timestamps) - len(set(timestamps))
    invalid_ohlc = sum(
        1 for c in candles if c.high < max(c.open, c.close) or c.low > min(c.open, c.close)
    )
    negative_volume = sum(1 for c in candles if c.volume < 0)
    non_monotonic = sum(1 for a, b in zip(timestamps, timestamps[1:]) if b <= a)
    gaps = sum(
        1
        for a, b in zip(sorted(set(timestamps)), sorted(set(timestamps))[1:])
        if b - a != expected_interval_ms
    )
    return CandleQuality(
        len(candles), duplicates, invalid_ohlc, negative_volume, non_monotonic, gaps
    )


def sample_quality(trades: int) -> str:
    if trades < 30:
        return "VERY LOW SAMPLE"
    if trades <= 100:
        return "LOW SAMPLE"
    if trades <= 300:
        return "MODERATE SAMPLE"
    return "BETTER SAMPLE"
