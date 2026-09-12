import io
import json
from urllib.parse import parse_qs, urlparse

from src.binance import BinanceMarketStream, BinancePrivateClient, BinancePublicClient


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


def test_private_account_request_uses_hmac_signature(monkeypatch):
    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured["request"] = request
        return FakeResponse(json.dumps({"balances": []}).encode())

    monkeypatch.setattr("src.binance.urlopen", fake_urlopen)
    result = BinancePrivateClient("public-key", "private-secret", "https://example.test").account_information()
    query = parse_qs(urlparse(captured["request"].full_url).query)
    assert result == {"balances": []}
    assert captured["request"].headers["X-mbx-apikey"] == "public-key"
    assert len(query["signature"][0]) == 64


def test_market_stream_builds_combined_stream_url():
    assert BinanceMarketStream("wss://example.test/stream").stream_url(["BTCUSDT", "ETHUSDT"]) == "wss://example.test/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker"
