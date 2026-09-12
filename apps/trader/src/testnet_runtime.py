"""Authenticated Binance Spot Testnet runtime using the same strategy path."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .account_stream import UserDataStreamManager
from .binance import BinancePrivateClient, BinancePublicClient, BinanceUserDataStream
from .core import RiskEngine
from .database import (
    latest_account_balances,
    local_open_order_ids,
    reserve_trade_intent,
    save_account_balances,
    save_candles,
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


@dataclass
class TestnetRuntime:
    market_client: BinancePublicClient
    account_client: BinancePrivateClient
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    poll_seconds: int = 60
    reconcile_seconds: int = 300

    def __post_init__(self) -> None:
        self.broker = BinanceSpotBroker(
            self.account_client,
            trading_mode="testnet",
        )
        self.engine = PaperEngine(
            PaperEngineConfig(symbol=self.symbol),
            risk=RiskEngine(),
            broker=self.broker,
            before_submit=lambda intent, _decision: reserve_trade_intent(intent, "testnet"),
        )
        self.state = "not_configured" if not self.account_client.configured else "starting"
        self.last_run_at: datetime | None = None
        self.last_candle_at: datetime | None = None
        self.last_reconciliation_at: datetime | None = None
        self.last_error: str | None = None
        self.reconciliation_status = "NOT_CONFIGURED"
        self.cycles = 0
        self._bootstrapped = False
        self.error_count = 0
        self.user_stream = UserDataStreamManager(
            self.account_client,
            BinanceUserDataStream("wss://stream.testnet.binance.vision/ws"),
            on_account_event=self._on_account_event,
            on_reconnect=self._on_stream_reconnect,
        )

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
                self._persist_snapshot()
                emit_alert(
                    "testnet cycle failed",
                    symbol=self.symbol,
                    event="testnet_cycle_error",
                    error=str(exc),
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
            self._persist_snapshot()

    async def _on_account_event(self, event: dict[str, object]) -> None:
        if str(event.get("e", "")) in {
            "executionReport",
            "outboundAccountPosition",
            "balanceUpdate",
        }:
            await self._reconcile()

    async def _on_stream_reconnect(self) -> None:
        self.engine.risk.hard_stop = True
        try:
            result = await self._reconcile()
            if result.status == "SYNCED":
                self.engine.risk.hard_stop = False
        except Exception as exc:  # noqa: BLE001 - fail closed until a later cycle reconciles
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
        quote_balance = next(
            (
                float(item["free"]) + float(item["locked"])
                for item in balances
                if item["asset"] == "USDT"
            ),
            0.0,
        )
        if quote_balance <= 0:
            raise RuntimeError("Testnet account has no USDT balance")
        self.engine = PaperEngine(
            PaperEngineConfig(symbol=self.symbol, starting_cash=quote_balance),
            risk=RiskEngine(),
            broker=self.broker,
            before_submit=lambda intent, _decision: reserve_trade_intent(intent, "testnet"),
        )
        exchange_info = await asyncio.to_thread(self.market_client.exchange_info, self.symbol)
        rows = exchange_info.get("symbols", [])
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            self.broker.filters[self.symbol] = SymbolFilters.from_exchange_info(rows[0])
        self._bootstrapped = True

    async def _reconcile(self) -> ReconciliationResult:
        result = await asyncio.to_thread(
            AccountReconciler().reconcile,
            self.account_client,
            local_balances=latest_account_balances(),
            local_open_order_ids=local_open_order_ids(),
        )
        self.last_reconciliation_at = datetime.now(timezone.utc)
        self.reconciliation_status = result.status
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
                cycles=self.cycles,
                errors=self.error_count,
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
        }

    def _closed_candles(self, candles: list[Candle]) -> list[Candle]:
        interval_ms = 60 * 60 * 1000
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return [candle for candle in candles if candle.open_time + interval_ms <= now_ms]
