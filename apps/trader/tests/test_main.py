from fastapi import Response
from src.strategies import Candle

from src import main


def test_exchange_info_unwraps_binance_symbol_payload(monkeypatch):
    monkeypatch.setattr(
        main.market_client,
        "exchange_info",
        lambda _symbol: {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.0001"}],
                }
            ]
        },
    )

    result = main.market_exchange_info(Response(), "BTCUSDT")

    assert result["symbol"] == "BTCUSDT"
    assert result["status"] == "TRADING"
    assert result["filters"][0]["filterType"] == "LOT_SIZE"


def test_binance_backtest_uses_public_closed_candles(monkeypatch):
    candles = [
        Candle(index, 100 + index, 102 + index, 99 + index, 101 + index, 1000)
        for index in range(90)
    ]
    monkeypatch.setattr(main.market_client, "klines", lambda *_args: candles)
    monkeypatch.setattr(main, "save_candles", lambda **_kwargs: len(candles))

    result = main.binance_backtest(Response(), "BTCUSDT", "1h", 500)

    assert result["source"] == "binance-public-spot-klines"
    assert result["data_points"] == 90
    assert result["persisted_candles"] == 90
    assert result["lookahead"] is False


def test_ready_fails_closed_for_unconfigured_testnet(monkeypatch):
    monkeypatch.setattr(main.settings, "trading_mode", "testnet")
    monkeypatch.setattr(main.settings, "live_trading_enabled", False)
    monkeypatch.setattr(main.settings, "binance_api_key", "")
    monkeypatch.setattr(main, "ping_db", lambda: True)

    result = main.ready()

    assert result.mode == "testnet"
    assert result.account_configured is False
    assert result.trading_enabled is False
