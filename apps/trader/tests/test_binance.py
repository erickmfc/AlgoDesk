import io
import json

from src.binance import BinancePublicClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_public_ticker_maps_symbol_and_price(monkeypatch):
    payload = json.dumps([{"symbol": "BTCUSDT", "price": "62340.10"}]).encode()
    monkeypatch.setattr("src.binance.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    result = BinancePublicClient("https://example.test").ticker_price(["BTCUSDT"])
    assert result[0].symbol == "BTCUSDT"
    assert result[0].price == 62340.10
