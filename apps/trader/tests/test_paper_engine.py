from src.binance import BinancePublicClient
from src.core import OrderSide, OrderStatus, PaperOrder, RiskConfig, RiskEngine, TradeIntent
from src.paper_engine import PaperEngine, PaperEngineConfig
from src.paper_runtime import PaperRuntime
from src.strategies import Candle
from src.testnet_runtime import bootstrap_entry_price, reconstructed_entry_price


def test_paper_engine_routes_signal_through_risk_and_order_manager():
    candles = [
        Candle(index, value, value + 1, value - 1, value)
        for index, value in enumerate([10, 9, 8, 9, 12, 14, 10, 7])
    ]
    engine = PaperEngine(
        PaperEngineConfig(
            starting_cash=1000,
            position_percent=50,
            fast_period=2,
            slow_period=4,
        ),
        risk=RiskEngine(
            RiskConfig(
                max_position_percent=50,
                max_total_exposure_percent=100,
                hard_drawdown_limit_percent=50,
            )
        ),
    )

    events = engine.process_closed_candles(candles)

    assert len(events) == 2
    assert all(event.order.status is OrderStatus.FILLED for event in events)
    assert all(event.order.fee > 0 for event in events)
    assert engine.snapshot()["trades"] == 1
    assert engine.snapshot()["open_positions"] == 0
    assert engine.process_closed_candles(candles) == []


def test_paper_engine_honors_atr_stop_from_strategy_config():
    candles = [
        Candle(index, value, value + 1, value - 1, value)
        for index, value in enumerate([10, 9, 8, 9, 12, 14, 9, 8])
    ]
    engine = PaperEngine(
        PaperEngineConfig(
            starting_cash=1_000,
            position_percent=50,
            fast_period=2,
            slow_period=4,
            atr_period=2,
            stop_loss_atr=1.0,
        ),
        risk=RiskEngine(
            RiskConfig(
                max_position_percent=50,
                max_total_exposure_percent=100,
                hard_drawdown_limit_percent=50,
            )
        ),
    )

    events = engine.process_closed_candles(candles)

    assert any(
        event.intent.side is OrderSide.SELL and event.intent.reason == "ATR stop loss reached"
        for event in events
    )
    assert engine.snapshot()["open_positions"] == 0


def test_paper_runtime_hard_stop_rejects_new_intents():
    runtime = PaperRuntime(BinancePublicClient())
    runtime.engine = PaperEngine(PaperEngineConfig(fast_period=2, slow_period=4))
    runtime.set_hard_stop(True)

    candles = [
        Candle(index, value, value + 1, value - 1, value)
        for index, value in enumerate([10, 9, 8, 9, 12, 14, 10, 7])
    ]
    events = runtime.engine.process_closed_candles(candles)

    assert runtime.summary()["hard_stop"] is True
    assert events
    assert all(event.order.status is OrderStatus.REJECTED for event in events)


def test_engine_restores_exchange_state_and_applies_stream_fill_once():
    engine = PaperEngine(PaperEngineConfig(starting_cash=1_000, fast_period=2, slow_period=4))
    engine.restore_account_state(cash=500, quantity=2, entry_price=90, mark_price=100)

    assert engine.snapshot()["equity"] == 700

    intent = TradeIntent(
        "ema-btc-01",
        "BTCUSDT",
        OrderSide.SELL,
        2,
        100,
        1,
    )
    order = PaperOrder("AD-T-stream", intent, OrderStatus.SUBMITTED)
    engine._orders_by_client_id[order.client_order_id] = (intent, order)

    assert engine.apply_execution_report(
        client_order_id="AD-T-stream",
        status="FILLED",
        cumulative_quantity=2,
        last_price=100,
    )
    after_first_fill = engine.snapshot()["equity"]
    assert engine.apply_execution_report(
        client_order_id="AD-T-stream",
        status="FILLED",
        cumulative_quantity=2,
        last_price=100,
    )
    assert engine.snapshot()["equity"] == after_first_fill


def test_external_broker_fill_waits_for_confirmed_user_stream_event():
    class ConfirmedBroker:
        def submit(self, intent, _decision):
            return PaperOrder(
                f"AD-T-{intent.idempotency_key}",
                intent,
                OrderStatus.FILLED,
                filled_quantity=intent.quantity,
            )

        def cancel_pending(self):
            return 0

    engine = PaperEngine(
        PaperEngineConfig(starting_cash=1_000, position_percent=10, fast_period=2, slow_period=4),
        broker=ConfirmedBroker(),
    )
    candles = [
        Candle(index, value, value + 1, value - 1, value)
        for index, value in enumerate([10, 9, 8, 9, 12, 14])
    ]

    events = engine.process_closed_candles(candles)

    assert engine.quantity == 0
    buy = next(event for event in events if event.intent.side is OrderSide.BUY)
    assert engine.apply_execution_report(
        client_order_id=buy.order.client_order_id,
        status="FILLED",
        cumulative_quantity=buy.intent.quantity,
        last_price=buy.intent.price,
    )
    assert engine.quantity == buy.intent.quantity


def test_testnet_position_restore_rebuilds_average_cost_from_fills():
    entry = reconstructed_entry_price(
        [
            {"time": 1, "isBuyer": True, "qty": "1", "price": "100"},
            {"time": 2, "isBuyer": True, "qty": "1", "price": "120"},
            {"time": 3, "isBuyer": False, "qty": "0.5", "price": "130"},
        ],
        expected_quantity=1.5,
        base_asset="BTC",
        quote_asset="USDT",
        tolerance=1e-8,
    )

    assert entry == 110


def test_testnet_bootstrap_marks_seeded_balance_without_trade_history():
    entry = bootstrap_entry_price(
        [],
        expected_quantity=0.5,
        base_asset="BTC",
        quote_asset="USDT",
        tolerance=1e-8,
        mark_price=50_000,
    )

    assert entry == 50_000
