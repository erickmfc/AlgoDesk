"""AlgoDesk API and worker entrypoint for Binance Spot research/trading modes.

Paper runs on real closed public candles. External execution is isolated behind
the mode-gated broker and remains locked unless the configured safety gates are
explicitly satisfied.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Literal
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .backtest import (
    BacktestConfig,
    run_backtest,
    run_backtest_splits,
    run_parameter_sweep,
    run_walk_forward,
)
from .binance import BinanceMarketStream, BinancePrivateClient, BinancePublicClient
from .config_loader import paper_engine_config_from_yaml, risk_config_from_yaml
from .core import RiskEngine
from .database import (
    init_db,
    latest_account_balances,
    latest_runtime_summary,
    local_fill_order_ids,
    local_open_order_ids,
    local_order_ids,
    ping_db,
    recent_paper_events,
    recent_runtime_equity,
    runtime_order_metrics,
    save_account_balances,
    save_candles,
    update_latest_runtime_reconciliation,
)
from .filters import SymbolFilters
from .monitoring import configure_logging
from .paper_runtime import PaperRuntime
from .reconciliation import AccountReconciler
from .settings import settings
from .strategies import Candle
from .testnet_runtime import TestnetRuntime

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global \
        database_available, \
        paper_runtime, \
        paper_task, \
        testnet_runtime, \
        testnet_task, \
        user_stream_task
    try:
        init_db()
        database_available = ping_db()
    except Exception:
        database_available = False
    if settings.application_role == "api":
        pass
    elif settings.trading_mode == "paper":
        paper_runtime = PaperRuntime(market_client)
        paper_task = asyncio.create_task(paper_runtime.loop())
    elif settings.trading_mode == "testnet":
        testnet_runtime = TestnetRuntime(
            market_client,
            account_client,
            reconcile_seconds=settings.reconciliation_interval_seconds,
        )
        if account_client.configured:
            testnet_task = asyncio.create_task(testnet_runtime.loop())
            user_stream_task = asyncio.create_task(testnet_runtime.account_stream_loop())
    yield
    if paper_task is not None:
        paper_task.cancel()
        with suppress(asyncio.CancelledError):
            await paper_task
        paper_task = None
    for task_name in ("testnet_task", "user_stream_task"):
        task = globals()[task_name]
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            globals()[task_name] = None


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


market_client = BinancePublicClient(settings.effective_binance_api_base_url)
market_stream = BinanceMarketStream(settings.effective_binance_ws_base_url)
account_client = BinancePrivateClient(
    settings.binance_api_key,
    settings.binance_api_secret.get_secret_value(),
    settings.effective_binance_api_base_url,
)
last_market_event_at: datetime | None = None
database_available = False
websocket_connections = 0
paper_runtime: PaperRuntime | None = None
paper_task: asyncio.Task[None] | None = None
testnet_runtime: TestnetRuntime | None = None
testnet_task: asyncio.Task[None] | None = None
user_stream_task: asyncio.Task[None] | None = None
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


def active_runtime() -> PaperRuntime | TestnetRuntime | None:
    return testnet_runtime if settings.trading_mode == "testnet" else paper_runtime


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
    account_configured = settings.account_configured
    trading_enabled = mode == "paper" or (
        mode in {"testnet", "live"} and account_configured and (mode == "testnet" or live_enabled)
    )
    return RuntimeStatus(
        mode=mode,
        live_trading_enabled=live_enabled,
        broker="paper" if mode in {"backtest", "paper"} else "binance-spot",
        trading_enabled=trading_enabled,
        database_connected=database_available,
        market_data_source="binance-public-spot",
        account_configured=account_configured,
    )


@app.get("/api/risk")
def risk_state() -> dict[str, object]:
    engine = RiskEngine(risk_config_from_yaml())
    runtime = active_runtime()
    stored = latest_runtime_summary(settings.trading_mode) if runtime is None else None
    return {
        "soft_stop": runtime.engine.risk.soft_stop if runtime else False,
        "hard_stop": runtime.engine.risk.hard_stop
        if runtime
        else bool(stored and stored["hard_stop"]),
        "config": engine.config.__dict__,
        "paper_portfolio": runtime.engine.portfolio.__dict__ if runtime else stored,
    }


@app.get("/api/paper/summary")
def paper_summary(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    runtime = active_runtime()
    if runtime is None:
        stored = latest_runtime_summary(settings.trading_mode)
        if stored is not None:
            return stored
        return {
            "source": "runtime-not-active",
            "mode": settings.trading_mode,
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
    return runtime.summary()


@app.get("/api/paper/events")
def paper_events(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    runtime = active_runtime()
    if runtime is None:
        mode = settings.trading_mode
        stored = latest_runtime_summary(mode)
        persisted = recent_paper_events(mode)
        return {
            "source": stored["source"] if stored else "runtime-not-active",
            "events": [
                {
                    "time": (
                        event["created_at"].astimezone(timezone.utc).strftime("%H:%M")
                        if isinstance(event["created_at"], datetime)
                        else "--:--"
                    ),
                    "bot": event["bot"],
                    "label": event["label"],
                    "tone": "cyan"
                    if event["label"] == "FILLED"
                    else "red"
                    if event["label"] == "REJECTED"
                    else "amber",
                    "text": f"{event['side']} {event['symbol']} @ ${float(str(event['price'])):,.2f} · {event['reason']}",
                }
                for event in persisted
            ],
        }
    events = []
    for event in reversed(runtime.engine.events[-20:]):
        status = event.order.status.value
        tone = "cyan" if status == "FILLED" else "red" if status == "REJECTED" else "amber"
        events.append(
            {
                "time": event.order.created_at.astimezone(timezone.utc).strftime("%H:%M"),
                "bot": event.intent.strategy_id,
                "label": status,
                "tone": tone,
                "text": f"{event.intent.side.value} {event.intent.symbol} @ ${event.intent.price:,.2f} · {event.intent.reason or event.decision.reason}",
            }
        )
    return {"source": runtime.summary()["source"], "events": events}


@app.get("/api/paper/equity")
def paper_equity(response: Response, limit: int = 60) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    mode = settings.trading_mode
    points = recent_runtime_equity(mode, limit)
    return {
        "source": "persisted-paper-snapshots",
        "mode": mode,
        "points": [
            {
                "captured_at": (
                    point["captured_at"].isoformat()
                    if isinstance(point["captured_at"], datetime)
                    else str(point["captured_at"])
                ),
                "equity": point["equity"],
            }
            for point in points
        ],
    }


@app.post("/api/paper/kill-switch")
def paper_kill_switch(request: PaperKillSwitchRequest) -> dict[str, object]:
    runtime = active_runtime()
    if runtime is None:
        if settings.application_role != "api":
            raise HTTPException(status_code=409, detail="paper runtime is not active")
        if not request.enabled and request.confirmation != "ENABLE":
            raise HTTPException(status_code=400, detail="confirmation ENABLE is required")
        try:
            payload = json.dumps(request.model_dump()).encode()
            remote = Request(
                f"{settings.trader_internal_url}/internal/paper/kill-switch",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(remote, timeout=5) as response:  # noqa: S310 - internal configured URL
                return json.load(response)
        except Exception as exc:  # noqa: BLE001 - surface a safe API error
            raise HTTPException(status_code=503, detail="trader worker is unavailable") from exc
    if not request.enabled and request.confirmation != "ENABLE":
        raise HTTPException(status_code=400, detail="confirmation ENABLE is required")
    if not request.enabled and settings.trading_mode == "testnet":
        if not getattr(runtime, "_bootstrapped", True):
            raise HTTPException(
                status_code=409,
                detail="Testnet account bootstrap is incomplete; reconcile the existing position before re-enabling",
            )
    runtime.set_hard_stop(request.enabled)
    return {
        "status": "HARD_STOP" if request.enabled else "RUNNING",
        "paper": runtime.summary(),
    }


@app.post("/internal/paper/kill-switch")
def internal_paper_kill_switch(request: PaperKillSwitchRequest) -> dict[str, object]:
    """Internal worker endpoint used by the API process in Compose."""
    runtime = active_runtime()
    if runtime is None:
        raise HTTPException(status_code=409, detail="paper runtime is not active")
    if not request.enabled and request.confirmation != "ENABLE":
        raise HTTPException(status_code=400, detail="confirmation ENABLE is required")
    if not request.enabled and settings.trading_mode == "testnet":
        if not getattr(runtime, "_bootstrapped", True):
            raise HTTPException(
                status_code=409,
                detail="Testnet account bootstrap is incomplete; reconcile the existing position before re-enabling",
            )
    runtime.set_hard_stop(request.enabled)
    return {
        "status": "HARD_STOP" if request.enabled else "RUNNING",
        "paper": runtime.summary(),
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
        "websocket_connected": market_stream.connected,
        "websocket_last_message_at": market_stream.last_message_at,
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
    runtime = active_runtime()
    persisted_runtime = latest_runtime_summary(settings.trading_mode) if runtime is None else None
    runtime_summary = runtime.summary() if runtime is not None else persisted_runtime
    connected_since = market_stream.connected_since
    websocket_uptime_seconds = (
        max(0.0, time.time() - connected_since) if connected_since is not None else 0.0
    )
    runtime_errors = runtime_summary.get("errors", 0) if runtime_summary else 0
    error_count = runtime_errors if isinstance(runtime_errors, int) else 0
    runtime_reconciliation_status = (
        str(runtime_summary.get("reconciliation_status") or reconciliation_status)
        if runtime_summary
        else reconciliation_status
    )
    runtime_last_reconciliation = (
        runtime_summary.get("last_reconciliation_at") if runtime_summary else None
    )
    return {
        "mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "database_connected": database_available,
        "account_configured": settings.account_configured,
        "market_data_source": "binance-public-spot",
        "last_market_event_at": last_market_event_at.isoformat() if last_market_event_at else None,
        "websocket_connections": websocket_connections,
        "websocket_connected": market_stream.connected,
        "websocket_uptime_seconds": websocket_uptime_seconds,
        "websocket_last_message_at": market_stream.last_message_at,
        "websocket_reconnects": market_stream.reconnects,
        "paper_runtime": runtime_summary,
        "orders": runtime_order_metrics(settings.trading_mode),
        "errors": error_count,
        "strategy_state": (
            "HALTED"
            if runtime_summary and runtime_summary.get("hard_stop")
            else str(runtime_summary.get("status", "UNKNOWN")).upper()
            if runtime_summary
            else "UNKNOWN"
        ),
        "reconciliation_status": runtime_reconciliation_status,
        "last_reconciliation_at": runtime_last_reconciliation
        or (last_reconciliation_at.isoformat() if last_reconciliation_at else None),
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
        balance_by_asset = {
            str(balance["asset"]).upper(): float(balance["free"]) + float(balance["locked"])
            for balance in balances
        }
        base_asset = "BTC"
        quote_asset = "USDT"
        mark_price: float | None = None
        ticker_by_symbol: dict[str, float] = {}
        try:
            ticker_by_symbol = {
                ticker.symbol.upper(): ticker.price
                for ticker in account_client.all_ticker_prices()
            }
            mark_price = ticker_by_symbol.get(f"{base_asset}{quote_asset}")
        except Exception:
            # Keep the raw account balances visible even when the mark price is temporarily unavailable.
            pass
        base_total = balance_by_asset.get(base_asset, 0.0)
        quote_total = balance_by_asset.get(quote_asset, 0.0)
        wallet_assets: list[dict[str, object]] = []
        wallet_value_quote = 0.0
        unpriced_assets: list[str] = []
        for balance in balances:
            asset = str(balance["asset"]).upper()
            total = float(balance["free"]) + float(balance["locked"])
            if asset == quote_asset:
                asset_value_quote = total
                asset_mark_price = 1.0
            else:
                asset_mark_price = ticker_by_symbol.get(f"{asset}{quote_asset}")
                asset_value_quote = total * asset_mark_price if asset_mark_price is not None else None
            if asset_value_quote is None:
                unpriced_assets.append(asset)
            else:
                wallet_value_quote += asset_value_quote
            wallet_assets.append(
                {
                    "asset": asset,
                    "total": total,
                    "mark_price": asset_mark_price,
                    "value_quote": asset_value_quote,
                }
            )
        return {
            "configured": True,
            "connected": True,
            "mode": settings.trading_mode,
            "balances": balances,
            "symbol": f"{base_asset}{quote_asset}",
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "base_total": base_total,
            "quote_total": quote_total,
            "mark_price": mark_price,
            "account_value_quote": quote_total + base_total * mark_price if mark_price else quote_total,
            "wallet_value_quote": wallet_value_quote,
            "wallet_assets": wallet_assets,
            "wallet_asset_count": len(wallet_assets),
            "wallet_unpriced_assets": unpriced_assets,
            "wallet_valuation_complete": not unpriced_assets,
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
def account_reconcile(response: Response, symbol: str = "BTCUSDT") -> dict[str, object]:
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
            local_open_order_ids=local_open_order_ids(settings.trading_mode),
            local_order_ids=local_order_ids(settings.trading_mode),
            local_fill_order_ids=local_fill_order_ids(settings.trading_mode),
            symbol=symbol.upper(),
            managed_client_prefix=(
                "AD-T-"
                if settings.trading_mode == "testnet"
                else "AD-L-"
                if settings.trading_mode == "live"
                else None
            ),
        )
        last_reconciliation_at = datetime.now(timezone.utc)
        reconciliation_status = result.status
        reconciliation_error = None
        update_latest_runtime_reconciliation(
            settings.trading_mode, result.status, last_reconciliation_at
        )
        return {
            "status": result.status,
            "balance_mismatches": result.balance_mismatches,
            "missing_local_orders": result.missing_local_orders,
            "unknown_remote_orders": result.unknown_remote_orders,
            "remote_open_orders": result.remote_open_orders,
            "missing_local_fills": result.missing_local_fills,
            "unknown_remote_fills": result.unknown_remote_fills,
            "remote_orders": result.remote_orders,
            "remote_fills": result.remote_fills,
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
    runtime_filters: SymbolFilters | None = None
    try:
        symbol_info = market_client.exchange_info(symbol).get("symbols", [])
        if isinstance(symbol_info, list) and symbol_info and isinstance(symbol_info[0], dict):
            runtime_filters = SymbolFilters.from_exchange_info(symbol_info[0])
    except Exception:
        # Historical research remains available if the optional filter lookup
        # is temporarily unavailable; the response exposes the assumption.
        runtime_filters = None
    strategy_config = paper_engine_config_from_yaml()
    config = BacktestConfig(
        fast_period=strategy_config.fast_period,
        slow_period=strategy_config.slow_period,
        atr_period=strategy_config.atr_period,
        stop_loss_atr=strategy_config.stop_loss_atr,
        take_profit_atr=strategy_config.take_profit_atr,
        position_percent=strategy_config.position_percent,
        fee_bps=strategy_config.fee_bps,
        spread_bps=2.0,
        latency_bars=1,
        min_quantity=float(runtime_filters.min_quantity) if runtime_filters else 0.0,
        min_notional=float(runtime_filters.min_notional) if runtime_filters else 0.0,
        tick_size=float(runtime_filters.tick_size) if runtime_filters else 0.0,
        step_size=float(runtime_filters.step_size) if runtime_filters else 0.0,
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
        "frictions": {
            "fee_bps": config.fee_bps,
            "slippage_bps": config.slippage_bps,
            "spread_bps": config.spread_bps,
            "latency_bars": config.latency_bars,
            "partial_fill_ratio": config.partial_fill_ratio,
            "filters_from_exchange_info": runtime_filters is not None,
        },
        "metrics": result.__dict__,
        "trades": len(trades),
        "splits": run_backtest_splits(candles, config),
        "parameter_sweep": run_parameter_sweep(candles, config),
        "walk_forward": run_walk_forward(candles, config),
    }
