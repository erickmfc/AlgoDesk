"""SQLAlchemy engine and small persistence boundary."""

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from .core import TradeIntent
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
    *,
    equity: float,
    starting_equity: float | None = None,
    daily_pnl: float,
    unrealized_pnl: float = 0.0,
    total_pnl: float | None = None,
    drawdown_percent: float,
    open_positions: int,
    mode: str = "paper",
    source: str = "paper-engine-from-binance-klines",
    allocation_percent: float = 0.0,
    trades: int = 0,
    win_rate: float = 0.0,
    status: str = "running",
    hard_stop: bool = False,
    last_run_at: datetime | None = None,
    last_candle_at: datetime | None = None,
    last_error: str | None = None,
    cycles: int = 0,
    errors: int = 0,
    reconciliation_status: str | None = None,
    last_reconciliation_at: datetime | None = None,
) -> None:
    with SessionLocal() as session:
        session.add(
            PortfolioSnapshotRecord(
                equity=equity,
                starting_equity=starting_equity if starting_equity is not None else equity,
                daily_pnl=daily_pnl,
                unrealized_pnl=unrealized_pnl,
                total_pnl=total_pnl if total_pnl is not None else daily_pnl + unrealized_pnl,
                open_positions=open_positions,
                drawdown_percent=drawdown_percent,
                mode=mode,
                source=source,
                allocation_percent=allocation_percent,
                trades=trades,
                win_rate=win_rate,
                status=status,
                hard_stop=int(hard_stop),
                last_run_at=last_run_at,
                last_candle_at=last_candle_at,
                last_error=last_error,
                cycles=cycles,
                errors=errors,
                reconciliation_status=reconciliation_status,
                last_reconciliation_at=last_reconciliation_at,
                captured_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def update_latest_runtime_reconciliation(mode: str, status: str, reconciled_at: datetime) -> bool:
    """Persist a read-only reconciliation result on the latest runtime snapshot."""
    with SessionLocal() as session:
        row = session.scalar(
            select(PortfolioSnapshotRecord)
            .where(PortfolioSnapshotRecord.mode == mode)
            .order_by(PortfolioSnapshotRecord.captured_at.desc())
        )
        if row is None:
            return False
        row.reconciliation_status = status
        row.last_reconciliation_at = reconciled_at
        session.commit()
        return True


def save_paper_events(events: Iterable[PaperEvent], mode: str = "paper") -> int:
    """Persist paper signals, intents, orders and fills idempotently.

    A PAPER worker replays a bounded closed-candle window after restart.  The
    same intent can therefore be observed again with a newer broker result
    (for example an old rejection becoming a filled protective exit after a
    risk-rule fix).  Treat the order row as an idempotent upsert and append an
    order event only when its observable state changed.
    """
    if not events:
        return 0
    with SessionLocal() as session:
        changed = 0
        for event in events:
            intent = event.intent
            order = event.order
            client_key = f"{mode.upper()}-{intent.idempotency_key}"
            order_id = client_key
            created_at = order.created_at
            reason = intent.reason or event.decision.reason
            raw_response = json.dumps(
                order.raw_response or {"broker": mode},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if session.get(SignalRecord, client_key) is None:
                session.add(
                    SignalRecord(
                        signal_id=client_key,
                        strategy_id=intent.strategy_id,
                        strategy_version=intent.strategy_version,
                        symbol=intent.symbol,
                        action=intent.side.value,
                        price=intent.price,
                        candle_timestamp=intent.candle_timestamp,
                        reason=reason,
                        created_at=created_at,
                    )
                )
                changed += 1
            else:
                signal = session.get(SignalRecord, client_key)
                if signal is not None and signal.reason != reason:
                    signal.reason = reason
                    changed += 1
            existing_intent = session.get(TradeIntentRecord, client_key)
            if existing_intent is None:
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
                        reason=reason,
                        status=order.status.value,
                        created_at=created_at,
                    )
                )
                changed += 1
            else:
                if existing_intent.reason != reason or existing_intent.status != order.status.value:
                    existing_intent.reason = reason
                    existing_intent.status = order.status.value
                    changed += 1

            existing_order = session.get(OrderRecord, order_id)
            if existing_order is None:
                session.add(
                    OrderRecord(
                        order_id=order_id,
                        client_order_id=order.client_order_id,
                        symbol=intent.symbol,
                        side=intent.side.value,
                        status=order.status.value,
                        raw_response=raw_response,
                        updated_at=created_at,
                    )
                )
                session.add(
                    OrderEventRecord(
                        order_id=order_id,
                        status=order.status.value,
                        details=reason,
                        created_at=created_at,
                    )
                )
                if order.filled_quantity > 0:
                    session.add(
                        FillRecord(
                            order_id=order_id,
                            price=intent.price,
                            quantity=order.filled_quantity,
                            fee=order.fee,
                            filled_at=created_at,
                        )
                    )
                changed += 1
                continue

            # Replays update the current idempotent order instead of leaving a
            # stale REJECTED/SUBMITTED row in the dashboard forever.
            observed_at = datetime.now(timezone.utc)
            if (
                existing_order.client_order_id != order.client_order_id
                or existing_order.symbol != intent.symbol
                or existing_order.side != intent.side.value
                or existing_order.status != order.status.value
                or existing_order.raw_response != raw_response
            ):
                existing_order.client_order_id = order.client_order_id
                existing_order.symbol = intent.symbol
                existing_order.side = intent.side.value
                existing_order.status = order.status.value
                existing_order.raw_response = raw_response
                existing_order.updated_at = observed_at
                changed += 1

            latest_event = session.scalar(
                select(OrderEventRecord)
                .where(OrderEventRecord.order_id == order_id)
                .order_by(OrderEventRecord.created_at.desc(), OrderEventRecord.id.desc())
            )
            if (
                latest_event is None
                or latest_event.status != order.status.value
                or latest_event.details != reason
            ):
                session.add(
                    OrderEventRecord(
                        order_id=order_id,
                        status=order.status.value,
                        details=reason,
                        created_at=observed_at,
                    )
                )
                existing_order.updated_at = observed_at
                changed += 1

            fills = session.scalars(select(FillRecord).where(FillRecord.order_id == order_id)).all()
            previous_quantity = sum(float(fill.quantity) for fill in fills)
            previous_fee = sum(float(fill.fee) for fill in fills)
            delta = max(0.0, float(order.filled_quantity) - previous_quantity)
            if delta > 1e-12:
                session.add(
                    FillRecord(
                        order_id=order_id,
                        price=intent.price,
                        quantity=delta,
                        fee=max(0.0, float(order.fee) - previous_fee),
                        filled_at=observed_at,
                    )
                )
                existing_order.updated_at = observed_at
                changed += 1
        if changed:
            session.commit()
        return changed


def save_execution_report(
    *,
    client_order_id: str,
    status: str,
    cumulative_quantity: float,
    last_price: float,
    raw_response: dict[str, object],
) -> bool:
    """Persist one Binance execution update and only its new fill delta."""
    status_map = {
        "NEW": "SUBMITTED",
        "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "FILLED": "FILLED",
        "CANCELED": "CANCELED",
        "REJECTED": "REJECTED",
        "EXPIRED": "CANCELED",
    }
    normalized_status = status_map.get(status.upper(), "UNKNOWN")
    with SessionLocal() as session:
        order = session.scalar(
            select(OrderRecord).where(OrderRecord.client_order_id == client_order_id)
        )
        if order is None:
            return False
        previous_quantity = sum(
            float(fill.quantity)
            for fill in session.scalars(
                select(FillRecord).where(FillRecord.order_id == order.order_id)
            ).all()
        )
        cumulative = max(0.0, float(cumulative_quantity))
        delta = max(0.0, cumulative - previous_quantity)
        now = datetime.now(timezone.utc)
        order.status = normalized_status
        order.raw_response = json.dumps(
            raw_response, ensure_ascii=False, sort_keys=True, default=str
        )
        order.updated_at = now
        intent = session.get(TradeIntentRecord, order.order_id)
        if intent is None and order.order_id.startswith(("PAPER-", "TESTNET-")):
            intent = session.get(TradeIntentRecord, order.order_id.split("-", 1)[1])
        if intent is not None:
            intent.status = normalized_status
        session.add(
            OrderEventRecord(
                order_id=order.order_id,
                status=normalized_status,
                details=f"Binance execution report: {status.upper()}",
                created_at=now,
            )
        )
        if delta > 1e-12 and last_price > 0:
            session.add(
                FillRecord(
                    order_id=order.order_id,
                    price=float(last_price),
                    quantity=delta,
                    fee=0.0,
                    filled_at=now,
                )
            )
        session.commit()
        return True


def reserve_trade_intent(intent: TradeIntent, mode: str = "paper") -> None:
    """Durably reserve an intent before an external broker call."""
    client_key = f"{mode.upper()}-{intent.idempotency_key}"
    with SessionLocal() as session:
        if session.get(TradeIntentRecord, client_key) is None:
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
                    reason=intent.reason or "intent reserved before broker submission",
                    status="CREATED",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()


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


def local_open_order_ids(mode: str = "paper") -> set[str]:
    """Return open client order ids for one execution mode."""
    prefix = f"{mode.upper()}-"
    with SessionLocal() as session:
        rows = session.scalars(
            select(OrderRecord.client_order_id).where(
                OrderRecord.order_id.like(f"{prefix}%"),
                OrderRecord.status.in_(
                    ("CREATED", "RISK_APPROVED", "SUBMITTING", "SUBMITTED", "PARTIALLY_FILLED")
                ),
            )
        ).all()
        return set(rows)


def local_order_ids(mode: str = "paper") -> set[str]:
    """Return every durable client order id for one execution mode."""
    prefix = f"{mode.upper()}-"
    with SessionLocal() as session:
        rows = session.scalars(
            select(OrderRecord.client_order_id).where(OrderRecord.order_id.like(f"{prefix}%"))
        ).all()
        return set(rows)


def local_fill_order_ids(mode: str = "paper") -> set[str]:
    """Return client ids for durable orders that have at least one fill."""
    prefix = f"{mode.upper()}-"
    with SessionLocal() as session:
        rows = session.scalars(
            select(OrderRecord.client_order_id)
            .join(FillRecord, FillRecord.order_id == OrderRecord.order_id)
            .where(OrderRecord.order_id.like(f"{prefix}%"))
            .distinct()
        ).all()
        return set(rows)


def runtime_order_metrics(mode: str = "paper") -> dict[str, int]:
    """Return durable order counts for the stateless API metrics surface."""
    prefix = f"{mode.upper()}-"
    open_statuses = {"CREATED", "RISK_APPROVED", "SUBMITTING", "SUBMITTED", "PARTIALLY_FILLED"}
    with SessionLocal() as session:
        orders = session.scalars(
            select(OrderRecord).where(OrderRecord.order_id.like(f"{prefix}%"))
        ).all()
        return {
            "total": len(orders),
            "open": sum(1 for order in orders if order.status in open_statuses),
        }


def latest_runtime_summary(mode: str = "paper") -> dict[str, object] | None:
    """Read the last worker snapshot so the API process stays stateless."""
    try:
        from .config_loader import paper_engine_config_from_yaml

        configured = paper_engine_config_from_yaml()
        configured_symbol = configured.symbol
        configured_interval = configured.interval
    except Exception:
        configured_symbol = "BTCUSDT"
        configured_interval = "1h"
    with SessionLocal() as session:
        row = session.scalar(
            select(PortfolioSnapshotRecord)
            .where(PortfolioSnapshotRecord.mode == mode)
            .order_by(PortfolioSnapshotRecord.captured_at.desc())
        )
        if row is None:
            return None
        return {
            "source": row.source,
            "mode": row.mode,
            "status": row.status,
            "symbol": configured_symbol,
            "interval": configured_interval,
            "equity": float(row.equity),
            "starting_equity": float(row.starting_equity),
            "daily_pnl": float(row.daily_pnl),
            "unrealized_pnl": float(row.unrealized_pnl),
            "total_pnl": float(row.total_pnl),
            "drawdown_percent": -abs(float(row.drawdown_percent)),
            "open_positions": int(row.open_positions),
            "allocation_percent": float(row.allocation_percent),
            "realized_pnl_24h": float(row.daily_pnl),
            "win_rate_24h": float(row.win_rate),
            "trades_24h": int(row.trades),
            "bot_count": 1,
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
            "last_candle_at": row.last_candle_at.isoformat() if row.last_candle_at else None,
            "last_error": row.last_error,
            "cycles": int(row.cycles),
            "hard_stop": bool(row.hard_stop),
            "errors": int(row.errors),
            "reconciliation_status": row.reconciliation_status or "NOT_CONFIGURED",
            "last_reconciliation_at": (
                row.last_reconciliation_at.isoformat() if row.last_reconciliation_at else None
            ),
        }


def recent_paper_events(mode: str = "paper", limit: int = 20) -> list[dict[str, object]]:
    """Read recent persisted order decisions for the API-only process.

    The audit tables retain every order, while this compact activity feed
    collapses identical visible messages from replayed candle windows.  The
    query is newest-first, so a current FILLED result wins over an older
    repeated rejection with the same symbol, side, price and reason.
    """
    prefix = f"{mode.upper()}-"
    with SessionLocal() as session:
        orders = session.scalars(
            select(OrderRecord)
            .where(OrderRecord.order_id.like(f"{prefix}%"))
            .order_by(OrderRecord.updated_at.desc())
            .limit(limit)
        ).all()
        result: list[dict[str, object]] = []
        visible_keys: set[tuple[str, str, str, float, str]] = set()
        for order in orders:
            intent = session.get(TradeIntentRecord, order.order_id)
            if intent is None and order.order_id.startswith(prefix):
                # Orders created before the mode prefix was introduced used
                # the raw idempotency hash as their intent key.
                intent = session.get(TradeIntentRecord, order.order_id.removeprefix(prefix))
            event = session.scalar(
                select(OrderEventRecord)
                .where(OrderEventRecord.order_id == order.order_id)
                .order_by(OrderEventRecord.created_at.desc())
            )
            if event is None and order.order_id.startswith(prefix):
                event = session.scalar(
                    select(OrderEventRecord)
                    .where(OrderEventRecord.order_id == order.order_id.removeprefix(prefix))
                    .order_by(OrderEventRecord.created_at.desc())
                )
            if intent is None:
                continue
            visible_key = (
                intent.strategy_id,
                intent.symbol,
                intent.side,
                round(float(intent.price), 8),
                event.details if event else intent.reason or "",
            )
            if visible_key in visible_keys:
                continue
            visible_keys.add(visible_key)
            result.append(
                {
                    "created_at": order.updated_at,
                    "bot": intent.strategy_id,
                    "label": order.status,
                    "symbol": intent.symbol,
                    "side": intent.side,
                    "price": float(intent.price),
                    "reason": event.details if event else intent.reason or "",
                }
            )
        return result


def recent_runtime_equity(mode: str = "paper", limit: int = 60) -> list[dict[str, object]]:
    """Return the persisted equity history in chronological order."""
    bounded_limit = min(max(limit, 1), 500)
    with SessionLocal() as session:
        rows = session.scalars(
            select(PortfolioSnapshotRecord)
            .where(PortfolioSnapshotRecord.mode == mode)
            .order_by(PortfolioSnapshotRecord.captured_at.desc())
            .limit(bounded_limit)
        ).all()
        return [
            {"captured_at": row.captured_at, "equity": float(row.equity)} for row in reversed(rows)
        ]
