"""Small, dependency-light trading domain used by the paper execution seam."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Protocol


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TradeIntent:
    strategy_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    candle_timestamp: int
    strategy_version: str = "v1"

    @property
    def idempotency_key(self) -> str:
        raw = ":".join(
            (
                self.strategy_id,
                self.symbol,
                str(self.candle_timestamp),
                self.side,
                self.strategy_version,
            )
        )
        return sha256(raw.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Portfolio:
    equity: float
    open_positions: int = 0
    total_exposure_percent: float = 0.0
    daily_loss_percent: float = 0.0
    drawdown_percent: float = 0.0
    balance_available: float = 0.0


@dataclass(frozen=True)
class RiskConfig:
    max_concurrent_positions: int = 2
    max_position_percent: float = 10.0
    max_total_exposure_percent: float = 25.0
    risk_per_trade_percent: float = 0.25
    daily_loss_limit_percent: float = 1.0
    hard_drawdown_limit_percent: float = 5.0
    stale_market_data_seconds: int = 30
    allow_margin: bool = False
    allow_futures: bool = False
    allow_leverage: bool = False


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    checks: tuple[str, ...] = ()


class RiskEngine:
    """One central gate for every intent produced by a strategy."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.soft_stop = False
        self.hard_stop = False

    def evaluate(
        self, intent: TradeIntent, portfolio: Portfolio, *, market_age_seconds: int = 0
    ) -> RiskDecision:
        checks = [
            "symbol valid",
            "quantity positive",
            "market data fresh",
            "balance available",
            "exposure within limit",
        ]
        if self.hard_stop:
            return RiskDecision(False, "hard kill switch active", tuple(checks))
        if self.soft_stop and intent.side is OrderSide.BUY:
            return RiskDecision(False, "soft kill switch active", tuple(checks))
        if intent.quantity <= 0 or intent.price <= 0:
            return RiskDecision(False, "quantity and price must be positive", tuple(checks))
        if market_age_seconds > self.config.stale_market_data_seconds:
            return RiskDecision(False, "market data is stale", tuple(checks))
        if (
            intent.side is OrderSide.BUY
            and portfolio.open_positions >= self.config.max_concurrent_positions
        ):
            return RiskDecision(False, "maximum concurrent positions reached", tuple(checks))
        position_value = intent.quantity * intent.price
        position_percent = position_value / portfolio.equity * 100 if portfolio.equity else 100
        if position_percent > self.config.max_position_percent:
            return RiskDecision(False, "position exposure exceeds limit", tuple(checks))
        if (
            portfolio.total_exposure_percent + position_percent
            > self.config.max_total_exposure_percent
        ):
            return RiskDecision(False, "portfolio exposure exceeds limit", tuple(checks))
        if portfolio.daily_loss_percent >= self.config.daily_loss_limit_percent:
            return RiskDecision(False, "daily loss limit reached", tuple(checks))
        if portfolio.drawdown_percent >= self.config.hard_drawdown_limit_percent:
            return RiskDecision(False, "hard drawdown limit reached", tuple(checks))
        if intent.side is OrderSide.BUY and position_value > portfolio.balance_available:
            return RiskDecision(False, "insufficient available balance", tuple(checks))
        return RiskDecision(True, "risk checks passed", tuple(checks))


@dataclass
class PaperOrder:
    client_order_id: str
    intent: TradeIntent
    status: OrderStatus = OrderStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_quantity: float = 0.0
    fee: float = 0.0
    raw_response: dict[str, object] | None = None


class BrokerAdapter(Protocol):
    def submit(self, intent: TradeIntent, decision: RiskDecision) -> PaperOrder: ...

    def cancel_pending(self) -> int: ...


class PaperBroker:
    """Deterministic paper broker. Duplicate intents return the same order."""

    def __init__(self) -> None:
        self.orders: dict[str, PaperOrder] = {}

    def submit(self, intent: TradeIntent, decision: RiskDecision) -> PaperOrder:
        existing = self.orders.get(intent.idempotency_key)
        if existing:
            return existing
        if not decision.approved:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.REJECTED)
            self.orders[intent.idempotency_key] = order
            return order
        order = PaperOrder(intent.idempotency_key, intent, OrderStatus.RISK_APPROVED)
        order.status = OrderStatus.SUBMITTED
        order.filled_quantity = intent.quantity
        order.status = OrderStatus.FILLED
        self.orders[intent.idempotency_key] = order
        return order

    def all_orders(self) -> Iterable[PaperOrder]:
        return self.orders.values()

    def cancel_pending(self) -> int:
        """Cancel every non-terminal paper order for the hard-stop path."""
        canceled = 0
        for order in self.orders.values():
            if order.status in {
                OrderStatus.SUBMITTING,
                OrderStatus.SUBMITTED,
                OrderStatus.PARTIALLY_FILLED,
            }:
                order.status = OrderStatus.CANCELED
                canceled += 1
        return canceled


class OrderManager:
    """Central execution boundary between RiskEngine and a broker adapter."""

    def __init__(self, broker: BrokerAdapter) -> None:
        self.broker = broker

    def submit(self, intent: TradeIntent, decision: RiskDecision) -> PaperOrder:
        return self.broker.submit(intent, decision)

    def cancel_pending(self) -> int:
        return self.broker.cancel_pending()
