import io
import json
from urllib.parse import parse_qs, urlparse

from src.binance import (
    BinanceMarketStream,
    BinancePrivateClient,
    BinancePublicClient,
    BinanceUserDataStream,
)


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
    result = BinancePrivateClient(
        "public-key", "private-secret", "https://example.test"
    ).account_information()
    query = parse_qs(urlparse(captured["request"].full_url).query)
    assert result == {"balances": []}
    assert captured["request"].headers["X-mbx-apikey"] == "public-key"
    assert len(query["signature"][0]) == 64


def test_market_stream_builds_combined_stream_url():
    assert (
        BinanceMarketStream("wss://example.test/stream").stream_url(["BTCUSDT", "ETHUSDT"])
        == "wss://example.test/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker"
    )


def test_public_klines_maps_closed_candle_fields(monkeypatch):
    payload = json.dumps(
        [[1700000000000, "100", "105", "98", "103", "1234", 1700003599999]]
    ).encode()
    monkeypatch.setattr("src.binance.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    result = BinancePublicClient("https://example.test").klines("BTCUSDT", "1h", 1)
    assert result[0].open_time == 1700000000000
    assert result[0].high == 105.0
    assert result[0].close == 103.0
    assert result[0].volume == 1234.0


def test_private_read_only_open_orders_is_signed(monkeypatch):
    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured["request"] = request
        return FakeResponse(b"[]")

    monkeypatch.setattr("src.binance.urlopen", fake_urlopen)
    result = BinancePrivateClient(
        "public-key", "private-secret", "https://example.test"
    ).open_orders("BTCUSDT")
    assert result == []
    assert "/api/v3/openOrders" in captured["request"].full_url
    assert parse_qs(urlparse(captured["request"].full_url).query)["symbol"] == ["BTCUSDT"]


def test_user_data_stream_uses_listen_key_url():
    assert (
        BinanceUserDataStream("wss://example.test/ws").stream_url("listen-key")
        == "wss://example.test/ws/listen-key"
    )
