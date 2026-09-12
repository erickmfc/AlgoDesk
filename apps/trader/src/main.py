"""AlgoDesk read-only service seam for paper trading and public market data.

Trading remains disabled until authenticated execution, persistence and
reconciliation gates are implemented and explicitly enabled.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .binance import BinanceMarketStream, BinancePrivateClient, BinancePublicClient
from .backtest import BacktestConfig, run_backtest
from .core import Portfolio, RiskEngine, RiskConfig
from .database import init_db, ping_db, save_paper_snapshot
from .settings import settings
from .strategies import Candle

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global database_available
    try:
        init_db()
        database_available = ping_db()
    except Exception:
        database_available = False
    yield


app = FastAPI(title="AlgoDesk Trader", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)
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


class RuntimeStatus(BaseModel):
    mode: Literal["backtest", "paper", "testnet", "live"]
    live_trading_enabled: bool
    broker: str
    trading_enabled: bool
    database_connected: bool
    market_data_source: str
    account_configured: bool


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
        "sample_portfolio": Portfolio(equity=12428.50, balance_available=12428.50).__dict__,
    }


@app.get("/api/paper/summary")
def paper_summary(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    snapshot = {
        "source": "local-paper-snapshot",
        "mode": "paper",
        "equity": 12428.50,
        "daily_pnl": 342.18,
        "drawdown_percent": -3.12,
        "open_positions": 2,
        "realized_pnl_24h": 298.65,
        "win_rate_24h": 75.0,
        "trades_24h": 12,
        "bot_count": 5,
    }
    try:
        save_paper_snapshot(
            equity=snapshot["equity"],
            daily_pnl=snapshot["daily_pnl"],
            drawdown_percent=abs(snapshot["drawdown_percent"]),
            open_positions=snapshot["open_positions"],
        )
    except Exception:
        pass
    return snapshot


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
    }


@app.websocket("/ws/market")
async def market_socket(websocket: WebSocket) -> None:
    global last_market_event_at, websocket_connections
    await websocket.accept()
    websocket_connections += 1
    symbols = [value.strip().upper() for value in websocket.query_params.get("symbols", "BTCUSDT,ETHUSDT").split(",") if value.strip()][:5]
    await websocket.send_json({"type": "status", "status": "connecting", "source": "binance-websocket"})
    try:
        async for ticker in market_stream.iter_tickers(symbols):
            last_market_event_at = datetime.now(timezone.utc)
            await websocket.send_json({"type": "ticker", "source": "binance-websocket", "symbol": ticker.symbol, "price": ticker.price})
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
        balances = [
            {"asset": row["asset"], "free": float(row["free"]), "locked": float(row["locked"])}
            for row in payload.get("balances", [])
            if isinstance(row, dict) and float(row.get("free", 0)) + float(row.get("locked", 0)) > 0
        ]
        return {"configured": True, "connected": True, "mode": settings.trading_mode, "balances": balances}
    except Exception:
        return {
            "configured": True,
            "connected": False,
            "mode": settings.trading_mode,
            "balances": [],
            "message": "Binance account read failed; no trading action was attempted",
        }


@app.get("/api/backtests/demo")
def demo_backtest() -> dict[str, object]:
    closes = [100 - (index * 0.25) for index in range(35)]
    closes += [91.25 + (index * 0.55) + ((index % 5) * 0.08) for index in range(45)]
    closes += [116 - (index * 0.5) + ((index % 4) * 0.06) for index in range(40)]
    candles = [Candle(index, close - 0.5, close + 1.4, close - 1.2, close, 1000) for index, close in enumerate(closes)]
    result, trades = run_backtest(candles, BacktestConfig(fast_period=8, slow_period=21, position_percent=10))
    return {"mode": "backtest", "symbol": "DEMOUSDT", "metrics": result.__dict__, "trades": len(trades)}
