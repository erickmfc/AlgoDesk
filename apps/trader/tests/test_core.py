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


def test_risk_fails_closed_until_account_and_api_are_healthy() -> None:
    engine = RiskEngine()
    engine.account_synchronized = False
    assert engine.evaluate(intent(), portfolio()).reason == "account is not synchronized"

    engine.account_synchronized = True
    engine.api_healthy = False
    assert engine.evaluate(intent(), portfolio()).reason == "Binance API health check failed"


def test_risk_respects_risk_per_trade_when_stop_is_defined() -> None:
    risky_intent = TradeIntent(
        "ema-btc-01",
        "BTCUSDT",
        OrderSide.BUY,
        1.0,
        100.0,
        1700000000,
        stop_price=90.0,
    )

    decision = RiskEngine(RiskConfig(risk_per_trade_percent=0.05)).evaluate(
        risky_intent, Portfolio(equity=1000.0, balance_available=1000.0)
    )

    assert decision.approved is False
    assert decision.reason == "risk per trade exceeds limit"


def test_risk_allows_protective_sell_when_limits_are_reached() -> None:
    protective_sell = TradeIntent(
        "ema-btc-01",
        "BTCUSDT",
        OrderSide.SELL,
        0.2,
        100.0,
        1700000000,
    )
    stressed = Portfolio(
        equity=1000.0,
        open_positions=1,
        total_exposure_percent=50.0,
        daily_loss_percent=5.0,
        drawdown_percent=10.0,
        balance_available=0.0,
    )

    decision = RiskEngine().evaluate(protective_sell, stressed)

    assert decision.approved is True


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
