"""SQLAlchemy engine and small persistence boundary."""

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    AccountBalanceRecord,
    Base,
    CandleRecord,
    FillRecord,
    OrderEventRecord,
    OrderRecord,
    PortfolioSnapshotRecord,
    SignalRecord,
    TradeIntentRecord,
)
from .paper_engine import PaperEvent
from .settings import settings
from .strategies import Candle


def _engine_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return url


DATABASE_URL = _engine_url()
engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def ping_db() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def save_candles(
    *, symbol: str, interval: str, candles: list[Candle], exchange: str = "binance"
) -> int:
    """Persist closed market candles without duplicating the exchange/time key."""
    if not candles:
        return 0
    with SessionLocal() as session:
        existing = set(
            session.scalars(
                select(CandleRecord.open_time).where(
                    CandleRecord.exchange == exchange,
                    CandleRecord.symbol == symbol,
                    CandleRecord.interval == interval,
                )
            ).all()
        )
        existing_ms = {
            int(
                (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).timestamp()
                * 1000
            )
            for value in existing
        }
        inserted = 0
        for candle in candles:
            if candle.open_time in existing_ms:
                continue
            session.add(
                CandleRecord(
                    exchange=exchange,
                    symbol=symbol,
                    interval=interval,
                    open_time=datetime.fromtimestamp(candle.open_time / 1000, tz=timezone.utc),
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
            )
            existing_ms.add(candle.open_time)
            inserted += 1
        if inserted:
            session.commit()
        return inserted


def save_paper_snapshot(
    *, equity: float, daily_pnl: float, drawdown_percent: float, open_positions: int
) -> None:
    with SessionLocal() as session:
        session.add(
            PortfolioSnapshotRecord(
                equity=equity,
                daily_pnl=daily_pnl,
                open_positions=open_positions,
                drawdown_percent=drawdown_percent,
                mode="paper",
                captured_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def save_paper_events(events: Iterable[PaperEvent]) -> int:
    """Persist paper signals, intents, orders and fills idempotently."""
    if not events:
        return 0
    with SessionLocal() as session:
        inserted = 0
        for event in events:
            intent = event.intent
            order = event.order
            client_key = intent.idempotency_key
            order_id = f"PAPER-{client_key}"
            if session.get(OrderRecord, order_id) is not None:
                continue
            created_at = order.created_at
            session.add(
                SignalRecord(
                    signal_id=client_key,
                    strategy_id=intent.strategy_id,
                    strategy_version=intent.strategy_version,
                    symbol=intent.symbol,
                    action=intent.side.value,
                    price=intent.price,
                    candle_timestamp=intent.candle_timestamp,
                    reason=event.decision.reason,
                    created_at=created_at,
                )
            )
            session.add(
                TradeIntentRecord(
                    client_key=client_key,
                    strategy_id=intent.strategy_id,
                    symbol=intent.symbol,
                    side=intent.side.value,
                    quantity=intent.quantity,
                    price=intent.price,
                    candle_timestamp=intent.candle_timestamp,
                    strategy_version=intent.strategy_version,
                    reason=event.decision.reason,
                    status=order.status.value,
                    created_at=created_at,
                )
            )
            session.add(
                OrderRecord(
                    order_id=order_id,
                    client_order_id=order.client_order_id,
                    symbol=intent.symbol,
                    side=intent.side.value,
                    status=order.status.value,
                    raw_response='{"broker":"paper"}',
                    updated_at=created_at,
                )
            )
            session.add(
                OrderEventRecord(
                    order_id=order_id,
                    status=order.status.value,
                    details=event.decision.reason,
                    created_at=created_at,
                )
            )
            if order.status.value == "FILLED":
                session.add(
                    FillRecord(
                        order_id=order_id,
                        price=intent.price,
                        quantity=order.filled_quantity,
                        fee=order.fee,
                        filled_at=created_at,
                    )
                )
            inserted += 1
        if inserted:
            session.commit()
        return inserted


def save_account_balances(balances: list[dict[str, float | str]]) -> int:
    if not balances:
        return 0
    captured_at = datetime.now(timezone.utc)
    with SessionLocal() as session:
        for balance in balances:
            session.add(
                AccountBalanceRecord(
                    asset=str(balance["asset"]),
                    free=float(balance["free"]),
                    locked=float(balance["locked"]),
                    source="binance",
                    captured_at=captured_at,
                )
            )
        session.commit()
    return len(balances)


def latest_account_balances() -> dict[str, float]:
    with SessionLocal() as session:
        latest = session.scalar(
            select(AccountBalanceRecord.captured_at).order_by(
                AccountBalanceRecord.captured_at.desc()
            )
        )
        if latest is None:
            return {}
        rows = session.scalars(
            select(AccountBalanceRecord).where(AccountBalanceRecord.captured_at == latest)
        ).all()
        return {row.asset: row.free + row.locked for row in rows}


def local_open_order_ids() -> set[str]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(OrderRecord.client_order_id).where(
                OrderRecord.status.in_(
                    ("CREATED", "RISK_APPROVED", "SUBMITTING", "SUBMITTED", "PARTIALLY_FILLED")
                )
            )
        ).all()
        return set(rows)
