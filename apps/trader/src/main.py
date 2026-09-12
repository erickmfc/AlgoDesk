"""AlgoDesk read-only service seam for paper trading and public market data.

Trading remains disabled until authenticated execution, persistence and
reconciliation gates are implemented and explicitly enabled.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .backtest import BacktestConfig, run_backtest
from .binance import BinanceMarketStream, BinancePrivateClient, BinancePublicClient
from .core import RiskConfig, RiskEngine
from .database import (
    init_db,
    latest_account_balances,
    local_open_order_ids,
    ping_db,
    save_account_balances,
    save_candles,
)
from .paper_runtime import PaperRuntime
from .reconciliation import AccountReconciler
from .settings import settings
from .strategies import Candle


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global database_available, paper_runtime, paper_task
    try:
        init_db()
        database_available = ping_db()
    except Exception:
        database_available = False
    if settings.trading_mode == "paper":
        paper_runtime = PaperRuntime(market_client)
        paper_task = asyncio.create_task(paper_runtime.loop())
    yield
    if paper_task is not None:
        paper_task.cancel()
        with suppress(asyncio.CancelledError):
            await paper_task
        paper_task = None


app = FastAPI(title="AlgoDesk Trader", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


BINANCE_INTERVAL_SECONDS = {
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
}


def periods_per_year(interval: str) -> float:
    seconds = BINANCE_INTERVAL_SECONDS.get(interval)
    if seconds is None:
        raise ValueError(f"unsupported Binance interval: {interval}")
    return (365 * 24 * 60 * 60) / seconds


def closed_candles(candles: list[Candle], interval: str) -> list[Candle]:
    interval_ms = BINANCE_INTERVAL_SECONDS[interval] * 1000
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return [candle for candle in candles if candle.open_time + interval_ms <= now_ms]


market_client = BinancePublicClient(settings.binance_api_base_url)
market_stream = BinanceMarketStream(settings.binance_ws_base_url)
account_client = BinancePrivateClient(
    settings.binance_api_key,
    settings.binance_api_secret.get_secret_value(),
    settings.binance_api_base_url,
)
last_market_event_at: datetime | None = None
database_available = False
websocket_connections = 0
paper_runtime: PaperRuntime | None = None
paper_task: asyncio.Task[None] | None = None
last_reconciliation_at: datetime | None = None
reconciliation_status = "NOT_CONFIGURED"
reconciliation_error: str | None = None


class RuntimeStatus(BaseModel):
    mode: Literal["backtest", "paper", "testnet", "live"]
    live_trading_enabled: bool
    broker: str
    trading_enabled: bool
    database_connected: bool
    market_data_source: str
    account_configured: bool


class PaperKillSwitchRequest(BaseModel):
    enabled: bool
    confirmation: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "trader"}


@app.get("/ready", response_model=RuntimeStatus)
def ready() -> RuntimeStatus:
    global database_available
    # Containers can become ready a moment after the API process starts. Probe
    # on demand so a transient startup race never leaves readiness stale.
    database_available = ping_db()
    mode = settings.trading_mode
    live_enabled = settings.live_trading_enabled
    return RuntimeStatus(
        mode=mode,
        live_trading_enabled=live_enabled,
        broker="paper" if mode in {"backtest", "paper"} else "binance-spot",
        trading_enabled=mode in {"paper", "testnet"} or (mode == "live" and live_enabled),
        database_connected=database_available,
        market_data_source="binance-public-spot",
        account_configured=settings.account_configured,
    )


@app.get("/api/risk")
def risk_state() -> dict[str, object]:
    engine = RiskEngine(RiskConfig())
    return {
        "soft_stop": engine.soft_stop,
        "hard_stop": engine.hard_stop,
        "config": engine.config.__dict__,
        "paper_portfolio": paper_runtime.engine.portfolio.__dict__ if paper_runtime else None,
    }


@app.get("/api/paper/summary")
def paper_summary(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    if paper_runtime is None:
        return {
            "source": "paper-engine-from-binance-klines",
            "mode": "paper",
            "status": "disabled",
            "equity": 0.0,
            "daily_pnl": 0.0,
            "drawdown_percent": 0.0,
            "open_positions": 0,
            "realized_pnl_24h": 0.0,
            "win_rate_24h": 0.0,
            "trades_24h": 0,
            "bot_count": 1,
            "hard_stop": False,
            "last_error": "paper runtime is not active",
        }
    return paper_runtime.summary()


@app.get("/api/paper/events")
def paper_events(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    if paper_runtime is None:
        return {"source": "paper-engine-from-binance-klines", "events": []}
    events = []
    for event in reversed(paper_runtime.engine.events[-20:]):
        status = event.order.status.value
        tone = "cyan" if status == "FILLED" else "red" if status == "REJECTED" else "amber"
        events.append(
            {
                "time": event.order.created_at.astimezone(timezone.utc).strftime("%H:%M"),
                "bot": event.intent.strategy_id,
                "label": status,
                "tone": tone,
                "text": f"{event.intent.side.value} {event.intent.symbol} @ ${event.intent.price:,.2f} · {event.decision.reason}",
            }
        )
    return {"source": "paper-engine-from-binance-klines", "events": events}


@app.post("/api/paper/kill-switch")
def paper_kill_switch(request: PaperKillSwitchRequest) -> dict[str, object]:
    if paper_runtime is None:
        raise HTTPException(status_code=409, detail="paper runtime is not active")
    if not request.enabled and request.confirmation != "ENABLE":
        raise HTTPException(status_code=400, detail="confirmation ENABLE is required")
    paper_runtime.set_hard_stop(request.enabled)
    return {
        "status": "HARD_STOP" if request.enabled else "RUNNING",
        "paper": paper_runtime.summary(),
    }


@app.get("/api/market/ticker")
def market_ticker(response: Response, symbol: str = "BTCUSDT,ETHUSDT") -> dict[str, object]:
    global last_market_event_at
    response.headers["Cache-Control"] = "no-store"
    symbols = [value.strip() for value in symbol.split(",") if value.strip()]
    tickers = market_client.ticker_price(symbols[:5])
    last_market_event_at = datetime.now(timezone.utc)
    return {"source": "binance-public-spot", "tickers": [ticker.__dict__ for ticker in tickers]}


@app.get("/api/market/status")
def market_status(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    return {
        "source": "binance-public-spot",
        "websocket": market_stream.stream_url(["BTCUSDT", "ETHUSDT"]),
        "last_market_event_at": last_market_event_at.isoformat() if last_market_event_at else None,
    }


@app.get("/api/market/exchange-info")
def market_exchange_info(response: Response, symbol: str = "BTCUSDT") -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    payload = market_client.exchange_info(symbol)
    symbol_rows = payload.get("symbols", [])
    symbol_info = symbol_rows[0] if isinstance(symbol_rows, list) and symbol_rows else payload
    if not isinstance(symbol_info, dict):
        symbol_info = {}
    return {
        "source": "binance-public-spot",
        "symbol": symbol_info.get("symbol", symbol.upper()),
        "filters": symbol_info.get("filters", []),
        "status": symbol_info.get("status"),
    }


def candle_payload(candle: Candle) -> dict[str, object]:
    return {
        "open_time": candle.open_time,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


@app.get("/api/market/klines")
def market_klines(
    response: Response, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    if interval not in BINANCE_INTERVAL_SECONDS:
        raise HTTPException(status_code=400, detail=f"unsupported Binance interval: {interval}")
    candles = closed_candles(market_client.klines(symbol, interval, limit), interval)
    try:
        persisted = save_candles(symbol=symbol.upper(), interval=interval, candles=candles)
    except Exception:
        persisted = 0
    return {
        "source": "binance-public-spot-klines",
        "symbol": symbol.upper(),
        "interval": interval,
        "closed_candles": len(candles),
        "persisted_candles": persisted,
        "candles": [candle_payload(candle) for candle in candles],
    }


@app.get("/api/system/metrics")
def system_metrics(response: Response) -> dict[str, object]:
    global database_available
    response.headers["Cache-Control"] = "no-store"
    database_available = ping_db()
    return {
        "mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "database_connected": database_available,
        "account_configured": settings.account_configured,
        "market_data_source": "binance-public-spot",
        "last_market_event_at": last_market_event_at.isoformat() if last_market_event_at else None,
        "websocket_connections": websocket_connections,
        "websocket_reconnects": market_stream.reconnects,
        "paper_runtime": paper_runtime.summary() if paper_runtime is not None else None,
        "reconciliation_status": reconciliation_status,
        "last_reconciliation_at": last_reconciliation_at.isoformat()
        if last_reconciliation_at
        else None,
    }


@app.websocket("/ws/market")
async def market_socket(websocket: WebSocket) -> None:
    global last_market_event_at, websocket_connections
    await websocket.accept()
    websocket_connections += 1
    symbols = [
        value.strip().upper()
        for value in websocket.query_params.get("symbols", "BTCUSDT,ETHUSDT").split(",")
        if value.strip()
    ][:5]
    await websocket.send_json(
        {"type": "status", "status": "connecting", "source": "binance-websocket"}
    )
    try:
        async for ticker in market_stream.iter_tickers(symbols):
            last_market_event_at = datetime.now(timezone.utc)
            await websocket.send_json(
                {
                    "type": "ticker",
                    "source": "binance-websocket",
                    "symbol": ticker.symbol,
                    "price": ticker.price,
                }
            )
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        websocket_connections = max(0, websocket_connections - 1)


@app.get("/api/account/summary")
def account_summary(response: Response) -> dict[str, object]:
    """Return sanitized account balances only when server-side keys exist."""
    response.headers["Cache-Control"] = "no-store"
    if not account_client.configured:
        return {
            "configured": False,
            "connected": False,
            "mode": settings.trading_mode,
            "balances": [],
            "message": "Binance read-only credentials are not configured",
        }
    try:
        payload = account_client.account_information()
        raw_balances = payload.get("balances", [])
        if not isinstance(raw_balances, list):
            raw_balances = []
        balances = [
            {"asset": row["asset"], "free": float(row["free"]), "locked": float(row["locked"])}
            for row in raw_balances
            if isinstance(row, dict) and float(row.get("free", 0)) + float(row.get("locked", 0)) > 0
        ]
        save_account_balances(balances)
        return {
            "configured": True,
            "connected": True,
            "mode": settings.trading_mode,
            "balances": balances,
        }
    except Exception:
        return {
            "configured": True,
            "connected": False,
            "mode": settings.trading_mode,
            "balances": [],
            "message": "Binance account read failed; no trading action was attempted",
        }


@app.get("/api/account/reconcile")
def account_reconcile(response: Response) -> dict[str, object]:
    global last_reconciliation_at, reconciliation_status, reconciliation_error
    response.headers["Cache-Control"] = "no-store"
    if not account_client.configured:
        reconciliation_status = "NOT_CONFIGURED"
        return {
            "status": reconciliation_status,
            "message": "Binance read-only credentials are not configured",
        }
    try:
        result = AccountReconciler().reconcile(
            account_client,
            local_balances=latest_account_balances(),
            local_open_order_ids=local_open_order_ids(),
        )
        last_reconciliation_at = datetime.now(timezone.utc)
        reconciliation_status = result.status
        reconciliation_error = None
        return {
            "status": result.status,
            "balance_mismatches": result.balance_mismatches,
            "missing_local_orders": result.missing_local_orders,
            "unknown_remote_orders": result.unknown_remote_orders,
            "remote_open_orders": result.remote_open_orders,
        }
    except Exception as exc:
        reconciliation_status = "ERROR"
        reconciliation_error = str(exc)
        return {
            "status": reconciliation_status,
            "message": "Account reconciliation failed; trading remains paused",
        }


@app.get("/api/backtests/demo")
def demo_backtest() -> dict[str, object]:
    closes = [100 - (index * 0.25) for index in range(35)]
    closes += [91.25 + (index * 0.55) + ((index % 5) * 0.08) for index in range(45)]
    closes += [116 - (index * 0.5) + ((index % 4) * 0.06) for index in range(40)]
    candles = [
        Candle(index, close - 0.5, close + 1.4, close - 1.2, close, 1000)
        for index, close in enumerate(closes)
    ]
    result, trades = run_backtest(
        candles, BacktestConfig(fast_period=8, slow_period=21, position_percent=10)
    )
    return {
        "mode": "backtest",
        "symbol": "DEMOUSDT",
        "metrics": result.__dict__,
        "trades": len(trades),
    }


@app.get("/api/backtests/binance")
def binance_backtest(
    response: Response, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    if interval not in BINANCE_INTERVAL_SECONDS:
        raise HTTPException(status_code=400, detail=f"unsupported Binance interval: {interval}")
    requested_limit = min(max(limit, 100), 1000)
    candles = closed_candles(market_client.klines(symbol, interval, requested_limit), interval)
    config = BacktestConfig(
        fast_period=20,
        slow_period=50,
        position_percent=10,
        periods_per_year=periods_per_year(interval),
    )
    if len(candles) <= config.slow_period:
        raise HTTPException(
            status_code=422, detail="not enough closed candles for the configured strategy"
        )
    try:
        persisted = save_candles(symbol=symbol.upper(), interval=interval, candles=candles)
    except Exception:
        persisted = 0
    result, trades = run_backtest(candles, config)
    return {
        "mode": "backtest",
        "source": "binance-public-spot-klines",
        "symbol": symbol.upper(),
        "interval": interval,
        "data_points": len(candles),
        "persisted_candles": persisted,
        "data_start": datetime.fromtimestamp(
            candles[0].open_time / 1000, tz=timezone.utc
        ).isoformat(),
        "data_end": datetime.fromtimestamp(
            candles[-1].open_time / 1000, tz=timezone.utc
        ).isoformat(),
        "lookahead": False,
        "metrics": result.__dict__,
        "trades": len(trades),
    }
