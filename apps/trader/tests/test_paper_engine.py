from src.binance import BinancePublicClient
from src.core import OrderStatus, RiskConfig, RiskEngine
from src.paper_engine import PaperEngine, PaperEngineConfig
from src.paper_runtime import PaperRuntime
from src.strategies import Candle


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
