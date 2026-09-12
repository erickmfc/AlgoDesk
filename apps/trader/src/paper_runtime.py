"""Long-running PAPER cycle fed by Binance closed candles."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .binance import BinancePublicClient
from .database import save_candles, save_paper_events, save_paper_snapshot
from .paper_engine import PaperEngine, PaperEngineConfig
from .strategies import Candle

logger = logging.getLogger("algodesk.paper")


@dataclass
class PaperRuntime:
    market_client: BinancePublicClient
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    poll_seconds: int = 60

    def __post_init__(self) -> None:
        self.engine = PaperEngine(PaperEngineConfig(symbol=self.symbol))
        self.state = "starting"
        self.last_run_at: datetime | None = None
        self.last_candle_at: datetime | None = None
        self.last_error: str | None = None
        self.cycles = 0

    async def run_once(self) -> dict[str, object]:
        candles = await asyncio.to_thread(
            self.market_client.klines, self.symbol, self.interval, 500
        )
        closed = self._closed_candles(candles)
        if len(closed) <= self.engine.config.slow_period:
            raise RuntimeError("not enough closed candles for paper strategy")
        saved_candles = await asyncio.to_thread(
            save_candles, symbol=self.symbol, interval=self.interval, candles=closed
        )
        events = self.engine.process_closed_candles(closed)
        saved_events = await asyncio.to_thread(save_paper_events, events)
        snapshot = self.engine.snapshot()
        await asyncio.to_thread(
            save_paper_snapshot,
            equity=float(snapshot["equity"]),
            daily_pnl=float(snapshot["realized_pnl"]),
            drawdown_percent=float(snapshot["drawdown_percent"]),
            open_positions=int(snapshot["open_positions"]),
        )
        self.state = "running"
        self.last_error = None
        self.last_run_at = datetime.now(timezone.utc)
        self.last_candle_at = datetime.fromtimestamp(closed[-1].open_time / 1000, tz=timezone.utc)
        self.cycles += 1
        return {"saved_candles": saved_candles, "events": len(events), "saved_events": saved_events}

    async def loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep the paper loop alive and expose state
                self.state = "error"
                self.last_error = str(exc)
                logger.exception(
                    "paper cycle failed",
                    extra={"symbol": self.symbol, "event": "paper_cycle_error"},
                )
            await asyncio.sleep(self.poll_seconds)

    def summary(self) -> dict[str, object]:
        snapshot = self.engine.snapshot()
        return {
            "source": "paper-engine-from-binance-klines",
            "mode": "paper",
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
        }

    def set_hard_stop(self, enabled: bool) -> None:
        self.engine.risk.hard_stop = enabled
        if enabled:
            self.engine.orders.cancel_pending()

    def _closed_candles(self, candles: list[Candle]) -> list[Candle]:
        interval_ms = 60 * 60 * 1000
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return [candle for candle in candles if candle.open_time + interval_ms <= now_ms]
