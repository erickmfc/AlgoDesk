from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from src.models import Base, FillRecord, OrderEventRecord, OrderRecord, TradeIntentRecord

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
