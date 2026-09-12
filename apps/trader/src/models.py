"""PostgreSQL schema primitives for durable trading state."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CandleRecord(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("exchange", "symbol", "interval", "open_time"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange: Mapped[str] = mapped_column(String(24))
    symbol: Mapped[str] = mapped_column(String(24))
    interval: Mapped[str] = mapped_column(String(8))
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    high: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    low: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    close: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 10))


class StrategyRecord(Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    strategy_type: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str] = mapped_column(String(24))
    interval: Mapped[str] = mapped_column(String(8))
    version: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class TradeIntentRecord(Base):
    __tablename__ = "trade_intents"
    client_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(80))
    symbol: Mapped[str] = mapped_column(String(24))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderRecord(Base):
    __tablename__ = "orders"
    order_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(80), unique=True)
    symbol: Mapped[str] = mapped_column(String(24))
    side: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(24))
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FillRecord(Base):
    __tablename__ = "fills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(80))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioSnapshotRecord(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equity: Mapped[float] = mapped_column(Float)
    drawdown_percent: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskEventRecord(Base):
    __tablename__ = "risk_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SystemEventRecord(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BotStatusRecord(Base):
    __tablename__ = "bot_status"
    bot_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    state: Mapped[str] = mapped_column(String(24))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
