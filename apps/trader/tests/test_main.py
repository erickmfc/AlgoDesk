from fastapi import Response

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
