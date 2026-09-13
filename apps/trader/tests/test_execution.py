import io
from urllib.error import HTTPError

from src.binance import BinancePrivateClient
from src.core import (
    OrderSide,
    OrderStatus,
    Portfolio,
    RiskConfig,
    RiskDecision,
    RiskEngine,
    TradeIntent,
)
from src.execution import BinanceSpotBroker
from src.filters import SymbolFilters


def _intent() -> TradeIntent:
    return TradeIntent("ema-btc-01", "BTCUSDT", OrderSide.BUY, 0.01, 100.0, 1700000000)


def _decision() -> RiskDecision:
    intent = _intent()
    return RiskEngine(RiskConfig(max_position_percent=10)).evaluate(
        intent, Portfolio(equity=1000, balance_available=1000)
    )


def test_testnet_broker_maps_filled_order_and_is_idempotent(monkeypatch):
    client = BinancePrivateClient("key", "secret", "https://testnet.binance.vision")
    calls = []

    def place(**kwargs):
        calls.append(kwargs)
        return {"orderId": 42, "status": "FILLED", "executedQty": "0.01"}

    def query(**_kwargs):
        raise HTTPError("https://testnet.binance.vision", 400, "unknown order", {}, io.BytesIO())

    monkeypatch.setattr(client, "place_spot_limit_order", place)
    monkeypatch.setattr(client, "query_spot_order", query)
    broker = BinanceSpotBroker(
        client,
        trading_mode="testnet",
        filters={"BTCUSDT": SymbolFilters(symbol="BTCUSDT")},
    )
    first = broker.submit(_intent(), _decision())
    second = broker.submit(_intent(), _decision())

    assert first.status is OrderStatus.FILLED
    assert first.filled_quantity == 0.01
    assert first.raw_response == {"orderId": 42, "status": "FILLED", "executedQty": "0.01"}
    assert second.client_order_id == first.client_order_id
    assert len(calls) == 1


def test_live_broker_stays_locked_without_explicit_flag(monkeypatch):
    client = BinancePrivateClient("key", "secret", "https://api.binance.com")
    called = False

    def place(**_kwargs):
        nonlocal called
        called = True
        return {"orderId": 1, "status": "FILLED", "executedQty": "0.01"}

    monkeypatch.setattr(client, "place_spot_limit_order", place)
    order = BinanceSpotBroker(client, trading_mode="live", live_trading_enabled=False).submit(
        _intent(), _decision()
    )

    assert order.status is OrderStatus.REJECTED
    assert called is False


def test_testnet_broker_recovers_existing_remote_order(monkeypatch):
    client = BinancePrivateClient("key", "secret", "https://testnet.binance.vision")
    called = False

    def query(**_kwargs):
        return {"orderId": 42, "status": "FILLED", "executedQty": "0.01"}

    def place(**_kwargs):
        nonlocal called
        called = True
        return {"orderId": 43, "status": "FILLED", "executedQty": "0.01"}

    monkeypatch.setattr(client, "query_spot_order", query)
    monkeypatch.setattr(client, "place_spot_limit_order", place)
    broker = BinanceSpotBroker(
        client,
        trading_mode="testnet",
        filters={"BTCUSDT": SymbolFilters(symbol="BTCUSDT")},
    )

    order = broker.submit(_intent(), _decision())

    assert order.status is OrderStatus.FILLED
    assert order.filled_quantity == 0.01
    assert order.raw_response == {"orderId": 42, "status": "FILLED", "executedQty": "0.01"}
    assert called is False


def test_hard_stop_only_cancels_algodesk_managed_orders(monkeypatch):
    client = BinancePrivateClient("key", "secret", "https://testnet.binance.vision")
    canceled = []
    monkeypatch.setattr(
        client,
        "open_orders",
        lambda: [
            {"symbol": "BTCUSDT", "orderId": 1, "clientOrderId": "manual-order", "status": "NEW"},
            {"symbol": "BTCUSDT", "orderId": 2, "clientOrderId": "AD-T-managed", "status": "NEW"},
        ],
    )
    monkeypatch.setattr(
        client,
        "cancel_spot_order",
        lambda **kwargs: canceled.append(kwargs) or {"status": "CANCELED"},
    )

    assert BinanceSpotBroker(client, trading_mode="testnet").cancel_pending() == 1
    assert canceled == [{"symbol": "BTCUSDT", "order_id": "2", "client_order_id": "AD-T-managed"}]
