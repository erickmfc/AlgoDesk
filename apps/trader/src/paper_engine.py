"""Closed-candle PAPER runner that exercises the production order boundary."""

from collections.abc import Callable
from dataclasses import dataclass

from .core import (
    BrokerAdapter,
    OrderManager,
    OrderSide,
    OrderStatus,
    PaperBroker,
    PaperOrder,
    Portfolio,
    RiskConfig,
    RiskDecision,
    RiskEngine,
    TradeIntent,
)
from .strategies import Candle, EmaTrendStrategy, Signal


@dataclass(frozen=True)
class PaperEngineConfig:
    strategy_id: str = "ema-btc-01"
    strategy_version: str = "ema-trend-v1"
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    starting_cash: float = 10_000.0
    position_percent: float = 10.0
    fee_bps: float = 10.0
    fast_period: int = 20
    slow_period: int = 50
    atr_period: int = 14
    stop_loss_atr: float = 0.0
    take_profit_atr: float = 0.0


@dataclass(frozen=True)
class PaperEvent:
    intent: TradeIntent
    decision: RiskDecision
    order: PaperOrder


class PaperEngine:
    """Run one strategy through intent, risk, order manager and paper broker."""

    def __init__(
        self,
        config: PaperEngineConfig | None = None,
        risk: RiskEngine | None = None,
        broker: BrokerAdapter | None = None,
        before_submit: Callable[[TradeIntent, RiskDecision], None] | None = None,
    ) -> None:
        self.config = config or PaperEngineConfig()
        self.risk = risk or RiskEngine(RiskConfig())
        self.broker = broker or PaperBroker()
        self.orders = OrderManager(self.broker)
        self.before_submit = before_submit
        self.strategy = EmaTrendStrategy(
            self.config.fast_period,
            self.config.slow_period,
            self.config.atr_period,
            self.config.stop_loss_atr,
            self.config.take_profit_atr,
        )
        self.cash = self.config.starting_cash
        self.quantity = 0.0
        self.entry_price = 0.0
        self.entry_fee = 0.0
        self.realized_pnl = 0.0
        self.closed_trade_pnls: list[float] = []
        self.fees_paid = 0.0
        self.last_price = self.config.starting_cash
        self.peak_equity = self.config.starting_cash
        self.processed_signals: set[int] = set()
        self.events: list[PaperEvent] = []
        self._orders_by_client_id: dict[str, tuple[TradeIntent, PaperOrder]] = {}
        self._applied_fill_quantity: dict[str, float] = {}
        self.stop_price: float | None = None
        self.take_profit_price: float | None = None
        self._pending_exit = False

    def process_closed_candles(
        self, candles: list[Candle], *, market_age_seconds: int = 0
    ) -> list[PaperEvent]:
        if not candles:
            return []
        self.last_price = candles[-1].close
        new_events: list[PaperEvent] = []
        signals_by_timestamp = {
            signal.timestamp: signal for signal in self.strategy.signals(candles)
        }
        for candle in candles:
            if self.quantity > 0 and not self._pending_exit:
                exit_signal: Signal | None = None
                if self.stop_price is not None and candle.low <= self.stop_price:
                    exit_signal = Signal(
                        candle.open_time,
                        "SELL",
                        self.stop_price,
                        "ATR stop loss reached",
                    )
                elif self.take_profit_price is not None and candle.high >= self.take_profit_price:
                    exit_signal = Signal(
                        candle.open_time,
                        "SELL",
                        self.take_profit_price,
                        "ATR take profit reached",
                    )
                if exit_signal is not None:
                    event = self._submit_signal(exit_signal, market_age_seconds=market_age_seconds)
                    if event is not None:
                        new_events.append(event)
                    if exit_signal.timestamp in self.processed_signals:
                        continue
            signal = signals_by_timestamp.get(candle.open_time)
            if signal is not None:
                event = self._submit_signal(signal, market_age_seconds=market_age_seconds)
                if event is not None:
                    new_events.append(event)
        self.last_price = candles[-1].close
        self._update_peak()
        return new_events

    def _submit_signal(self, signal: Signal, *, market_age_seconds: int) -> PaperEvent | None:
        if signal.timestamp in self.processed_signals:
            return None
        self.processed_signals.add(signal.timestamp)
        if signal.action == "BUY" and self.quantity > 0:
            return None
        if signal.action == "SELL" and self.quantity <= 0:
            return None
        # Risk is evaluated against the same closed-candle price that
        # generated the signal, not against a later mark in the batch.
        self.last_price = signal.price
        quantity = (
            ((self.cash * self.config.position_percent / 100) / signal.price)
            if signal.action == "BUY"
            else self.quantity
        )
        if signal.action == "BUY" and signal.stop_price is not None:
            risk_budget = self.portfolio.equity * self.risk.config.risk_per_trade_percent / 100
            risk_per_unit = signal.price - signal.stop_price
            if risk_per_unit > 0:
                quantity = min(quantity, risk_budget / risk_per_unit)
        intent = TradeIntent(
            self.config.strategy_id,
            self.config.symbol,
            OrderSide(signal.action),
            quantity,
            signal.price,
            signal.timestamp,
            self.config.strategy_version,
            stop_price=signal.stop_price,
            take_profit_price=signal.take_profit_price,
            reason=signal.reason,
        )
        decision = self.risk.evaluate(intent, self.portfolio, market_age_seconds=market_age_seconds)
        if decision.approved and signal.reason in {
            "ATR stop loss reached",
            "ATR take profit reached",
        }:
            decision = RiskDecision(True, signal.reason, decision.checks)
        if self.before_submit is not None:
            self.before_submit(intent, decision)
        if decision.approved and signal.action == "BUY":
            self.stop_price = signal.stop_price
            self.take_profit_price = signal.take_profit_price
        order = self.orders.submit(intent, decision)
        event = PaperEvent(intent, decision, order)
        self.events.append(event)
        self._orders_by_client_id[order.client_order_id] = (intent, order)
        if isinstance(self.broker, PaperBroker) and order.status in {
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
        }:
            self._apply_cumulative_fill(intent, order, order.filled_quantity, intent.price)
        if signal.action == "SELL" and order.status in {
            OrderStatus.SUBMITTING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.UNKNOWN,
        }:
            self._pending_exit = True
        return event

    def restore_account_state(
        self,
        *,
        cash: float,
        quantity: float,
        entry_price: float,
        mark_price: float,
    ) -> None:
        """Initialize a Testnet engine from reconciled exchange balances.

        This deliberately resets local PnL statistics: historical account PnL
        belongs to Binance, while subsequent strategy events are measured from
        the restored mark.  Invalid account state is rejected before a worker
        can create any intent.
        """
        if cash < 0 or quantity < 0 or mark_price <= 0 or (quantity > 0 and entry_price <= 0):
            raise ValueError("invalid restored account state")
        self.cash = cash
        self.quantity = quantity
        self.entry_price = entry_price if quantity else 0.0
        self.entry_fee = 0.0
        self.realized_pnl = 0.0
        self.closed_trade_pnls = []
        self.fees_paid = 0.0
        self.last_price = mark_price
        self.peak_equity = self.equity
        self.stop_price = None
        self.take_profit_price = None
        self._pending_exit = False

    def apply_execution_report(
        self,
        *,
        client_order_id: str,
        status: str,
        cumulative_quantity: float,
        last_price: float,
    ) -> bool:
        """Apply only the unaccounted fill delta from a Binance user-stream event."""
        tracked = self._orders_by_client_id.get(client_order_id)
        if tracked is None:
            return False
        intent, order = tracked
        status_map = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.CANCELED,
        }
        order.status = status_map.get(status.upper(), OrderStatus.UNKNOWN)
        order.filled_quantity = max(order.filled_quantity, cumulative_quantity)
        self._apply_cumulative_fill(intent, order, cumulative_quantity, last_price or intent.price)
        if intent.side is OrderSide.SELL and order.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        }:
            self._pending_exit = False
        self._update_peak()
        return True

    @property
    def equity(self) -> float:
        return self.cash + self.quantity * self.last_price

    @property
    def portfolio(self) -> Portfolio:
        exposure = (self.quantity * self.last_price / self.equity * 100) if self.equity else 0.0
        drawdown = (
            ((self.peak_equity - self.equity) / self.peak_equity * 100) if self.peak_equity else 0.0
        )
        return Portfolio(
            equity=self.equity,
            open_positions=1 if self.quantity > 0 else 0,
            total_exposure_percent=exposure,
            daily_loss_percent=max(0.0, -self.realized_pnl / self.config.starting_cash * 100),
            drawdown_percent=drawdown,
            balance_available=self.cash,
        )

    def snapshot(self) -> dict[str, float | int]:
        closed_trades = len(self.closed_trade_pnls)
        return {
            "equity": self.equity,
            "realized_pnl": self.realized_pnl,
            "fees": self.fees_paid,
            "open_positions": 1 if self.quantity > 0 else 0,
            "allocation_percent": self.portfolio.total_exposure_percent,
            "trades": closed_trades,
            "win_rate": (sum(1 for pnl in self.closed_trade_pnls if pnl > 0) / closed_trades * 100)
            if closed_trades
            else 0.0,
            "drawdown_percent": self.portfolio.drawdown_percent,
        }

    def _apply_cumulative_fill(
        self, intent: TradeIntent, order: PaperOrder, cumulative_quantity: float, price: float
    ) -> None:
        applied = self._applied_fill_quantity.get(order.client_order_id, 0.0)
        quantity = max(0.0, cumulative_quantity - applied)
        if quantity <= 1e-12:
            return
        self._applied_fill_quantity[order.client_order_id] = applied + quantity
        notional = quantity * price
        fee = notional * self.config.fee_bps / 10_000
        order.fee += fee
        self.fees_paid += fee
        if intent.side is OrderSide.BUY:
            self.cash -= notional + fee
            previous_notional = self.quantity * self.entry_price
            self.quantity += quantity
            self.entry_price = (
                (previous_notional + notional) / self.quantity if self.quantity else 0.0
            )
            self.entry_fee += fee
        else:
            self.cash += notional - fee
            closing_quantity = min(quantity, self.quantity)
            allocated_entry_fee = (
                self.entry_fee * (closing_quantity / self.quantity) if self.quantity else 0.0
            )
            trade_pnl = (price - self.entry_price) * closing_quantity - allocated_entry_fee - fee
            self.realized_pnl += trade_pnl
            self.closed_trade_pnls.append(trade_pnl)
            self.quantity = max(0.0, self.quantity - closing_quantity)
            self.entry_fee = max(0.0, self.entry_fee - allocated_entry_fee)
            if self.quantity == 0:
                self.entry_price = 0.0
                self.entry_fee = 0.0
                self.stop_price = None
                self.take_profit_price = None
                self._pending_exit = False

    def _update_peak(self) -> None:
        self.peak_equity = max(self.peak_equity, self.equity)
