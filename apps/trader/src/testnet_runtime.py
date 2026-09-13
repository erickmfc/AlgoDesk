"""Authenticated Binance Spot Testnet runtime using the same strategy path."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .account_stream import UserDataStreamManager
from .binance import (
    BinancePrivateClient,
    BinancePublicClient,
    BinanceWebSocketUserDataStream,
)
from .config_loader import paper_engine_config_from_yaml, risk_config_from_yaml
from .core import RiskEngine
from .database import (
    latest_account_balances,
    local_fill_order_ids,
    local_open_order_ids,
    local_order_ids,
    reserve_trade_intent,
    save_account_balances,
    save_candles,
    save_execution_report,
    save_paper_events,
    save_paper_snapshot,
)
from .execution import BinanceSpotBroker
from .filters import SymbolFilters
from .monitoring import emit_alert
from .paper_engine import PaperEngine, PaperEngineConfig
from .reconciliation import AccountReconciler, ReconciliationResult
from .strategies import Candle

logger = logging.getLogger("algodesk.testnet")


def _as_bool(value: object) -> bool:
    return value is True or str(value).lower() == "true"


def reconstructed_entry_price(
    trades: list[dict[str, object]],
    *,
    expected_quantity: float,
    base_asset: str,
    quote_asset: str,
    tolerance: float,
) -> float:
    """Rebuild the remaining Spot position with an average-cost ledger.

    A mismatch is intentionally fatal to startup: guessing an inherited
    position's cost or quantity would let the strategy trade on untrusted
    local state.  Commission in either base or quote is included when Binance
    reports it; third-asset commissions do not change the position quantity.
    """
    quantity = 0.0
    cost = 0.0
    for trade in sorted(trades, key=lambda row: int(str(row.get("time", 0)))):
        try:
            executed = float(str(trade.get("qty", 0)))
            price = float(str(trade.get("price", 0)))
            commission = float(str(trade.get("commission", 0)))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Testnet trade history contains an invalid fill") from exc
        if executed <= 0 or price <= 0:
            continue
        commission_asset = str(trade.get("commissionAsset", "")).upper()
        if _as_bool(trade.get("isBuyer")):
            received = executed - (commission if commission_asset == base_asset else 0.0)
            if received < -tolerance:
                raise RuntimeError("Testnet base-asset commission exceeds buy quantity")
            cost += executed * price + (commission if commission_asset == quote_asset else 0.0)
            quantity += max(0.0, received)
            continue
        consumed = executed + (commission if commission_asset == base_asset else 0.0)
        if consumed > quantity + tolerance:
            raise RuntimeError("Testnet trade history sells more base asset than it buys")
        average_cost = cost / quantity if quantity else 0.0
        consumed = min(consumed, quantity)
        cost -= average_cost * consumed
        quantity -= consumed
    if abs(quantity - expected_quantity) > tolerance:
        raise RuntimeError(
            "Testnet position cannot be restored from trade history; trading remains paused"
        )
    return cost / quantity if quantity > tolerance else 0.0


def bootstrap_entry_price(
    trades: list[dict[str, object]],
    *,
    expected_quantity: float,
    base_asset: str,
    quote_asset: str,
    tolerance: float,
    mark_price: float,
) -> float:
    """Choose a safe cost basis for a Testnet account's initial base balance.

    Binance Spot Testnet seeds new users with virtual balances, but those
    balances do not necessarily have matching trade history.  Treating an
    untracked initial balance as a position at the current mark avoids
    inventing historical PnL while preserving the strict mismatch check for
    accounts that do have fills we can reconstruct.
    """
    if expected_quantity <= tolerance:
        return 0.0
    if mark_price <= 0:
        raise ValueError("Testnet mark price must be positive")
    if not trades:
        return mark_price
    return reconstructed_entry_price(
        trades,
        expected_quantity=expected_quantity,
        base_asset=base_asset,
        quote_asset=quote_asset,
        tolerance=tolerance,
    )


@dataclass
class TestnetRuntime:
    market_client: BinancePublicClient
    account_client: BinancePrivateClient
    symbol: str = ""
    interval: str = ""
    poll_seconds: int = 60
    reconcile_seconds: int = 300

    def __post_init__(self) -> None:
        configured = paper_engine_config_from_yaml()
        self.symbol = self.symbol or configured.symbol
        self.interval = self.interval or configured.interval
        self.broker = BinanceSpotBroker(
            self.account_client,
            trading_mode="testnet",
        )
        self.engine = PaperEngine(
            self._engine_config(),
            risk=RiskEngine(risk_config_from_yaml()),
            broker=self.broker,
            before_submit=lambda intent, _decision: reserve_trade_intent(intent, "testnet"),
        )
        self.engine.risk.account_synchronized = not self.account_client.configured
        self.state = "not_configured" if not self.account_client.configured else "starting"
        self.last_run_at: datetime | None = None
        self.last_candle_at: datetime | None = None
        self.last_reconciliation_at: datetime | None = None
        self.last_error: str | None = None
        self.reconciliation_status = "NOT_CONFIGURED"
        self.cycles = 0
        self._bootstrapped = False
        self.error_count = 0
        self.base_asset = ""
        self.quote_asset = ""
        self.user_stream = UserDataStreamManager(
            self.account_client,
            BinanceWebSocketUserDataStream(
                self.account_client.api_key,
                self.account_client.api_secret,
                "wss://ws-api.testnet.binance.vision/ws-api/v3",
            ),
            on_account_event=self._on_account_event,
            on_reconnect=self._on_stream_reconnect,
            on_connected=self._on_stream_connected,
        )

    def _engine_config(self, *, starting_cash: float | None = None) -> PaperEngineConfig:
        configured = paper_engine_config_from_yaml()
        values = {**configured.__dict__, "symbol": self.symbol}
        if starting_cash is not None:
            values["starting_cash"] = starting_cash
        return PaperEngineConfig(**values)

    async def run_once(self) -> dict[str, object]:
        if not self.account_client.configured:
            self.state = "not_configured"
            self.last_error = "Binance Testnet credentials are not configured"
            return {"events": 0}
        await self._bootstrap_account()
        if (
            self.last_reconciliation_at is None
            or (datetime.now(timezone.utc) - self.last_reconciliation_at).total_seconds()
            >= self.reconcile_seconds
        ):
            await self._reconcile()
        if self.reconciliation_status == "DIVERGED":
            self.state = "trading_paused"
            return {"events": 0, "reconciliation": self.reconciliation_status}
        candles = await asyncio.to_thread(
            self.market_client.klines, self.symbol, self.interval, 500
        )
        closed = self._closed_candles(candles)
        if len(closed) <= self.engine.config.slow_period:
            raise RuntimeError("not enough closed candles for Testnet strategy")
        await asyncio.to_thread(
            save_candles, symbol=self.symbol, interval=self.interval, candles=closed
        )
        events = self.engine.process_closed_candles(closed)
        await asyncio.to_thread(save_paper_events, events, "testnet")
        snapshot = self.engine.snapshot()
        self.state = "running"
        self.last_error = None
        self.last_run_at = datetime.now(timezone.utc)
        self.last_candle_at = datetime.fromtimestamp(closed[-1].open_time / 1000, tz=timezone.utc)
        self.cycles += 1
        await asyncio.to_thread(
            save_paper_snapshot,
            equity=float(snapshot["equity"]),
            daily_pnl=float(snapshot["realized_pnl"]),
            drawdown_percent=float(snapshot["drawdown_percent"]),
            open_positions=int(snapshot["open_positions"]),
            mode="testnet",
            source="binance-spot-testnet",
            allocation_percent=float(snapshot["allocation_percent"]),
            trades=int(snapshot["trades"]),
            win_rate=float(snapshot["win_rate"]),
            status=self.state,
            hard_stop=self.engine.risk.hard_stop,
            last_run_at=self.last_run_at,
            last_candle_at=self.last_candle_at,
            cycles=self.cycles,
            errors=self.error_count,
            reconciliation_status=self.reconciliation_status,
            last_reconciliation_at=self.last_reconciliation_at,
        )
        return {"events": len(events), "reconciliation": self.reconciliation_status}

    async def loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - expose state and keep the loop alive
                self.state = "trading_paused"
                self.last_error = str(exc)
                self.error_count += 1
                self.engine.risk.hard_stop = True
                self.engine.risk.account_synchronized = False
                self._persist_snapshot()
                emit_alert(
                    "testnet cycle failed",
                    symbol=self.symbol,
                    event="testnet_cycle_error",
                    error=str(exc),
                )
                logger.exception(
                    "testnet cycle failed",
                    extra={
                        "symbol": self.symbol,
                        "event": "testnet_cycle_error",
                        "error": str(exc),
                    },
                )
            await asyncio.sleep(self.poll_seconds)

    async def account_stream_loop(self) -> None:
        try:
            await self.user_stream.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed on stream lifecycle errors
            self.state = "trading_paused"
            self.last_error = str(exc)
            self.engine.risk.hard_stop = True
            self.engine.risk.account_synchronized = False
            self._persist_snapshot()
            logger.exception(
                "testnet account stream failed",
                extra={
                    "symbol": self.symbol,
                    "event": "testnet_stream_error",
                    "error": str(exc),
                },
            )

    async def _on_account_event(self, event: dict[str, object]) -> None:
        event_type = str(event.get("e", ""))
        if event_type == "executionReport":
            try:
                client_order_id = str(event.get("c", ""))
                applied = self.engine.apply_execution_report(
                    client_order_id=client_order_id,
                    status=str(event.get("X", "UNKNOWN")),
                    cumulative_quantity=float(str(event.get("z", 0))),
                    last_price=float(str(event.get("L", 0))),
                )
                persisted = await asyncio.to_thread(
                    save_execution_report,
                    client_order_id=client_order_id,
                    status=str(event.get("X", "UNKNOWN")),
                    cumulative_quantity=float(str(event.get("z", 0))),
                    last_price=float(str(event.get("L", 0))),
                    raw_response=event,
                )
                if not applied or not persisted:
                    self.engine.risk.hard_stop = True
                    self.engine.risk.account_synchronized = False
                    self.last_error = "untracked Testnet execution report; trading paused"
                    emit_alert(
                        "untracked Testnet execution report",
                        symbol=self.symbol,
                        event="testnet_untracked_execution",
                        client_order_id=client_order_id,
                    )
            except (TypeError, ValueError) as exc:
                self.engine.risk.hard_stop = True
                self.last_error = f"invalid Testnet execution report: {exc}"
        if event_type in {
            "executionReport",
            "outboundAccountPosition",
            "balanceUpdate",
        }:
            await self._reconcile()

    async def _on_stream_reconnect(self) -> None:
        self.engine.risk.hard_stop = True
        self.engine.risk.account_synchronized = False
        try:
            await self._reconcile()
        except Exception as exc:  # noqa: BLE001 - fail closed until a later cycle reconciles
            self.last_error = str(exc)

    async def _on_stream_connected(self) -> None:
        if not self._bootstrapped:
            return
        try:
            result = await self._reconcile()
            if result.status == "SYNCED":
                self.engine.risk.hard_stop = False
                self.last_error = None
        except Exception as exc:  # noqa: BLE001 - fail closed until a later cycle reconciles
            self.engine.risk.hard_stop = True
            self.engine.risk.account_synchronized = False
            self.last_error = str(exc)

    async def _bootstrap_account(self) -> None:
        if self._bootstrapped:
            return
        payload = await asyncio.to_thread(self.account_client.account_information)
        raw_balances = payload.get("balances", [])
        balances = (
            [
                {
                    "asset": row["asset"],
                    "free": float(row.get("free", 0)),
                    "locked": float(row.get("locked", 0)),
                }
                for row in raw_balances
                if isinstance(row, dict) and "asset" in row
            ]
            if isinstance(raw_balances, list)
            else []
        )
        save_account_balances(balances)
        exchange_info = await asyncio.to_thread(self.market_client.exchange_info, self.symbol)
        rows = exchange_info.get("symbols", [])
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise RuntimeError("Binance Testnet exchange metadata is unavailable")
        symbol_info = rows[0]
        self.base_asset = str(symbol_info.get("baseAsset", "")).upper()
        self.quote_asset = str(symbol_info.get("quoteAsset", "")).upper()
        if not self.base_asset or not self.quote_asset:
            raise RuntimeError("Binance Testnet symbol metadata has no base/quote assets")
        self.broker.filters[self.symbol] = SymbolFilters.from_exchange_info(symbol_info)
        quote_balance = next(
            (
                float(item["free"]) + float(item["locked"])
                for item in balances
                if item["asset"] == self.quote_asset
            ),
            0.0,
        )
        base_balance = next(
            (
                float(item["free"]) + float(item["locked"])
                for item in balances
                if item["asset"] == self.base_asset
            ),
            0.0,
        )
        tickers = await asyncio.to_thread(self.market_client.ticker_price, [self.symbol])
        if not tickers or tickers[0].price <= 0:
            raise RuntimeError("Binance Testnet position cannot be marked without a Spot price")
        mark_price = tickers[0].price
        tolerance = max(float(self.broker.filters[self.symbol].step_size), 1e-8)
        entry_price = 0.0
        trade_count = 0
        if base_balance > tolerance:
            trades = await asyncio.to_thread(self.account_client.my_trades, self.symbol, 1000)
            trade_count = len(trades)
            entry_price = bootstrap_entry_price(
                trades,
                expected_quantity=base_balance,
                base_asset=self.base_asset,
                quote_asset=self.quote_asset,
                tolerance=tolerance,
                mark_price=mark_price,
            )
        if quote_balance <= 0 and base_balance <= tolerance:
            raise RuntimeError(
                f"Testnet account has no {self.quote_asset} or {self.base_asset} balance"
            )
        logger.info(
            "testnet account bootstrapped",
            extra={
                "event": "testnet_account_bootstrapped",
                "symbol": self.symbol,
                "error": (
                    f"base_balance={base_balance:.12g} quote_balance={quote_balance:.12g} "
                    f"trade_count={trade_count} entry_price={entry_price:.12g}"
                ),
            },
        )
        self.engine = PaperEngine(
            self._engine_config(starting_cash=quote_balance),
            risk=RiskEngine(risk_config_from_yaml()),
            broker=self.broker,
            before_submit=lambda intent, _decision: reserve_trade_intent(intent, "testnet"),
        )
        self.engine.restore_account_state(
            cash=quote_balance,
            quantity=base_balance,
            entry_price=entry_price,
            mark_price=mark_price,
        )
        self._bootstrapped = True

    async def _reconcile(self) -> ReconciliationResult:
        local_balances = latest_account_balances()
        if self._bootstrapped and self.base_asset and self.quote_asset:
            # Local expected base/quote balances come from confirmed fills and
            # restored account state, not from the last remote snapshot.
            local_balances = {
                **local_balances,
                self.base_asset: self.engine.quantity,
                self.quote_asset: self.engine.cash,
            }
        result = await asyncio.to_thread(
            AccountReconciler().reconcile,
            self.account_client,
            local_balances=local_balances,
            local_open_order_ids=local_open_order_ids("testnet"),
            local_order_ids=local_order_ids("testnet"),
            local_fill_order_ids=local_fill_order_ids("testnet"),
            symbol=self.symbol,
            managed_client_prefix="AD-T-",
        )
        self.last_reconciliation_at = datetime.now(timezone.utc)
        self.reconciliation_status = result.status
        self.engine.risk.account_synchronized = result.status == "SYNCED"
        if result.status == "DIVERGED":
            self.engine.risk.hard_stop = True
        return result

    def set_hard_stop(self, enabled: bool) -> None:
        self.engine.risk.hard_stop = enabled
        if enabled:
            self.engine.orders.cancel_pending()
        self._persist_snapshot()

    def _persist_snapshot(self) -> None:
        snapshot = self.engine.snapshot()
        try:
            save_paper_snapshot(
                equity=float(snapshot["equity"]),
                daily_pnl=float(snapshot["realized_pnl"]),
                drawdown_percent=float(snapshot["drawdown_percent"]),
                open_positions=int(snapshot["open_positions"]),
                mode="testnet",
                source="binance-spot-testnet",
                allocation_percent=float(snapshot["allocation_percent"]),
                trades=int(snapshot["trades"]),
                win_rate=float(snapshot["win_rate"]),
                status=self.state,
                hard_stop=self.engine.risk.hard_stop,
                last_run_at=self.last_run_at,
                last_candle_at=self.last_candle_at,
                last_error=self.last_error,
                cycles=self.cycles,
                errors=self.error_count,
                reconciliation_status=self.reconciliation_status,
                last_reconciliation_at=self.last_reconciliation_at,
            )
        except Exception as exc:  # noqa: BLE001 - fail-closed risk state stays in memory
            logger.warning("runtime snapshot persistence failed: %s", exc)

    def summary(self) -> dict[str, object]:
        snapshot = self.engine.snapshot()
        return {
            "source": "binance-spot-testnet",
            "mode": "testnet",
            "status": self.state,
            "symbol": self.symbol,
            "interval": self.interval,
            "equity": float(snapshot["equity"]),
            "daily_pnl": float(snapshot["realized_pnl"]),
            "drawdown_percent": -float(snapshot["drawdown_percent"]),
            "open_positions": int(snapshot["open_positions"]),
            "allocation_percent": float(snapshot["allocation_percent"]),
            "realized_pnl_24h": float(snapshot["realized_pnl"]),
            "win_rate_24h": float(snapshot["win_rate"]),
            "trades_24h": int(snapshot["trades"]),
            "bot_count": 1,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_candle_at": self.last_candle_at.isoformat() if self.last_candle_at else None,
            "last_error": self.last_error,
            "cycles": self.cycles,
            "hard_stop": self.engine.risk.hard_stop,
            "reconciliation_status": self.reconciliation_status,
            "errors": self.error_count,
            "last_reconciliation_at": self.last_reconciliation_at.isoformat()
            if self.last_reconciliation_at
            else None,
            "user_stream": {
                "state": self.user_stream.state,
                "connected": bool(getattr(self.user_stream.stream, "connected", False)),
                "reconnects": int(getattr(self.user_stream.stream, "reconnects", 0)),
                "last_event_at": self.user_stream.last_event_at.isoformat()
                if self.user_stream.last_event_at
                else None,
            },
        }

    def _closed_candles(self, candles: list[Candle]) -> list[Candle]:
        interval_ms = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "8h": 28800,
            "12h": 43200,
            "1d": 86400,
            "3d": 259200,
            "1w": 604800,
        }.get(self.interval)
        if interval_ms is None:
            raise ValueError(f"unsupported Binance interval: {self.interval}")
        interval_ms *= 1000
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return [candle for candle in candles if candle.open_time + interval_ms <= now_ms]
