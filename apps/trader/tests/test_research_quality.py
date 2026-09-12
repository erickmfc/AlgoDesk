from src.research_quality import inspect_candles, sample_quality
from src.strategies import Candle


def test_candle_quality_detects_invalid_values_and_gaps():
    candles = [Candle(0, 10, 9, 8, 10, 1), Candle(7200000, 10, 11, 9, 10, -1)]
    quality = inspect_candles(candles, 3600000)
    assert quality.invalid_ohlc == 1
    assert quality.negative_volume == 1
    assert quality.gaps == 1
    assert not quality.valid


def test_sample_quality_is_only_a_sample_size_warning():
    assert sample_quality(5) == "VERY LOW SAMPLE"
    assert sample_quality(50) == "LOW SAMPLE"
    assert sample_quality(150) == "MODERATE SAMPLE"
    assert sample_quality(301) == "BETTER SAMPLE"
