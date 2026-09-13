from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from src.core import OrderSide, OrderStatus, PaperOrder, RiskDecision, TradeIntent
from src.models import Base, FillRecord, OrderEventRecord, OrderRecord, TradeIntentRecord
from src.paper_engine import PaperEvent

from src import database


def test_execution_report_updates_order_and_deduplicates_cumulative_fill(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with sessions() as session:
        session.add(
            TradeIntentRecord(
                client_key="TESTNET-intent",
                strategy_id="ema-btc-01",
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.01,
                price=100.0,
                candle_timestamp=1,
                strategy_version="v1",
                status="CREATED",
                created_at=now,
            )
        )
        session.add(
            OrderRecord(
                order_id="TESTNET-intent",
                client_order_id="AD-T-intent",
                symbol="BTCUSDT",
                side="BUY",
                status="SUBMITTED",
                raw_response="{}",
                updated_at=now,
            )
        )
        session.commit()
    monkeypatch.setattr(database, "SessionLocal", sessions)

    report = {
        "e": "executionReport",
        "c": "AD-T-intent",
        "X": "PARTIALLY_FILLED",
        "z": "0.005",
        "L": "101.0",
    }
    assert database.save_execution_report(
        client_order_id="AD-T-intent",
        status="PARTIALLY_FILLED",
        cumulative_quantity=0.005,
        last_price=101.0,
        raw_response=report,
    )
    assert database.save_execution_report(
        client_order_id="AD-T-intent",
        status="PARTIALLY_FILLED",
        cumulative_quantity=0.005,
        last_price=101.0,
        raw_response=report,
    )

    with sessions() as session:
        order = session.get(OrderRecord, "TESTNET-intent")
        intent = session.get(TradeIntentRecord, "TESTNET-intent")
        fills = session.scalars(
            select(FillRecord).where(FillRecord.order_id == "TESTNET-intent")
        ).all()
        events = session.scalars(
            select(OrderEventRecord).where(OrderEventRecord.order_id == "TESTNET-intent")
        ).all()

    assert order is not None and order.status == "PARTIALLY_FILLED"
    assert intent is not None and intent.status == "PARTIALLY_FILLED"
    assert len(fills) == 1 and fills[0].quantity == 0.005
    assert len(events) == 2


def test_save_paper_events_upserts_replayed_order_state(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    now = datetime.now(timezone.utc)
    intent = TradeIntent(
        "ema-btc-01",
        "BTCUSDT",
        OrderSide.SELL,
        0.01,
        101.0,
        1,
        "ema-trend-v1",
        reason="ATR take profit reached",
    )

    rejected = PaperOrder(
        intent.idempotency_key,
        intent,
        OrderStatus.REJECTED,
        now,
        raw_response={"status": "REJECTED"},
    )
    filled = PaperOrder(
        intent.idempotency_key,
        intent,
        OrderStatus.FILLED,
        now,
        filled_quantity=0.01,
        fee=0.1,
        raw_response={"status": "FILLED"},
    )
    rejected_event = PaperEvent(intent, RiskDecision(False, "risk gate"), rejected)
    filled_event = PaperEvent(intent, RiskDecision(True, "risk checks passed"), filled)

    assert database.save_paper_events([rejected_event]) > 0
    assert database.save_paper_events([filled_event]) > 0
    assert database.save_paper_events([filled_event]) == 0

    with sessions() as session:
        order = session.get(OrderRecord, f"PAPER-{intent.idempotency_key}")
        fills = session.scalars(
            select(FillRecord).where(FillRecord.order_id == f"PAPER-{intent.idempotency_key}")
        ).all()
        events = session.scalars(
            select(OrderEventRecord).where(
                OrderEventRecord.order_id == f"PAPER-{intent.idempotency_key}"
            )
        ).all()

    assert order is not None and order.status == "FILLED"
    assert len(fills) == 1 and fills[0].quantity == 0.01
    assert len(events) == 2 and events[-1].status == "FILLED"
