"""Closed-candle PAPER runner that exercises the production order boundary."""

from dataclasses import dataclass

from .core import (
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
from .strategies import Candle, EmaTrendStrategy


@dataclass(frozen=True)
class PaperEngineConfig:
    strategy_id: str = "ema-btc-01"
    strategy_version: str = "ema-trend-v1"
    symbol: str = "BTCUSDT"
    starting_cash: float = 10_000.0
    position_percent: float = 10.0
    fee_bps: float = 10.0
    fast_period: int = 20
    slow_period: int = 50


@dataclass(frozen=True)
class PaperEvent:
    intent: TradeIntent
    decision: RiskDecision
    order: PaperOrder


class PaperEngine:
    """Run one strategy through intent, risk, order manager and paper broker."""

    def __init__(
        self, config: PaperEngineConfig | None = None, risk: RiskEngine | None = None
    ) -> None:
        self.config = config or PaperEngineConfig()
        self.risk = risk or RiskEngine(RiskConfig())
        self.broker = PaperBroker()
        self.orders = OrderManager(self.broker)
        self.strategy = EmaTrendStrategy(self.config.fast_period, self.config.slow_period)
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

    def process_closed_candles(
        self, candles: list[Candle], *, market_age_seconds: int = 0
    ) -> list[PaperEvent]:
        if not candles:
            return []
        self.last_price = candles[-1].close
        new_events: list[PaperEvent] = []
        for signal in self.strategy.signals(candles):
            if signal.timestamp in self.processed_signals:
                continue
            self.processed_signals.add(signal.timestamp)
            if signal.action == "BUY" and self.quantity > 0:
                continue
            if signal.action == "SELL" and self.quantity <= 0:
                continue
            # Risk is evaluated against the same closed-candle price that
            # generated the signal, not against a later mark in the batch.
            self.last_price = signal.price
            quantity = (
                ((self.cash * self.config.position_percent / 100) / signal.price)
                if signal.action == "BUY"
                else self.quantity
            )
            intent = TradeIntent(
                self.config.strategy_id,
                self.config.symbol,
                OrderSide(signal.action),
                quantity,
                signal.price,
                signal.timestamp,
                self.config.strategy_version,
            )
            decision = self.risk.evaluate(
                intent, self.portfolio, market_age_seconds=market_age_seconds
            )
            order = self.orders.submit(intent, decision)
            event = PaperEvent(intent, decision, order)
            self.events.append(event)
            new_events.append(event)
            if order.status is OrderStatus.FILLED:
                self._apply_fill(intent, order)
        self.last_price = candles[-1].close
        self._update_peak()
        return new_events

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

    def _apply_fill(self, intent: TradeIntent, order: PaperOrder) -> None:
        notional = intent.quantity * intent.price
        fee = notional * self.config.fee_bps / 10_000
        order.fee = fee
        self.fees_paid += fee
        if intent.side is OrderSide.BUY:
            self.cash -= notional + fee
            self.quantity += intent.quantity
            self.entry_price = intent.price
            self.entry_fee = fee
        else:
            self.cash += notional - fee
            trade_pnl = (intent.price - self.entry_price) * intent.quantity - self.entry_fee - fee
            self.realized_pnl += trade_pnl
            self.closed_trade_pnls.append(trade_pnl)
            self.quantity = max(0.0, self.quantity - intent.quantity)
            if self.quantity == 0:
                self.entry_price = 0.0
                self.entry_fee = 0.0

    def _update_peak(self) -> None:
        self.peak_equity = max(self.peak_equity, self.equity)
