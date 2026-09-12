from src.core import (
    OrderSide,
    OrderStatus,
    PaperBroker,
    Portfolio,
    RiskConfig,
    RiskEngine,
    TradeIntent,
)


def intent(quantity: float = 0.01) -> TradeIntent:
    return TradeIntent("ema-btc-01", "BTCUSDT", OrderSide.BUY, quantity, 100.0, 1700000000)


def portfolio() -> Portfolio:
    return Portfolio(equity=1000.0, balance_available=1000.0)


def test_risk_approves_small_paper_intent() -> None:
    decision = RiskEngine().evaluate(intent(), portfolio())
    assert decision.approved is True


def test_risk_rejects_stale_market_data() -> None:
    decision = RiskEngine().evaluate(intent(), portfolio(), market_age_seconds=31)
    assert decision.approved is False
    assert decision.reason == "market data is stale"


def test_risk_respects_hard_stop() -> None:
    engine = RiskEngine()
    engine.hard_stop = True
    decision = engine.evaluate(intent(), portfolio())
    assert decision.approved is False
    assert "hard kill" in decision.reason


def test_paper_broker_is_idempotent() -> None:
    broker = PaperBroker()
    engine = RiskEngine()
    first = broker.submit(intent(), engine.evaluate(intent(), portfolio()))
    second = broker.submit(intent(), engine.evaluate(intent(), portfolio()))
    assert first.client_order_id == second.client_order_id
    assert first.status is OrderStatus.FILLED
    assert len(list(broker.all_orders())) == 1


def test_paper_broker_persists_rejection() -> None:
    broker = PaperBroker()
    rejected_intent = intent(quantity=2)
    decision = RiskEngine(RiskConfig(max_position_percent=1)).evaluate(rejected_intent, portfolio())
    order = broker.submit(rejected_intent, decision)
    assert order.status is OrderStatus.REJECTED
