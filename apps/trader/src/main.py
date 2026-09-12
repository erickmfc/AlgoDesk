"""AlgoDesk read-only service seam for paper trading and public market data.

Trading remains disabled until authenticated execution, persistence and
reconciliation gates are implemented and explicitly enabled.
"""
import os
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .binance import BinancePublicClient
from .backtest import BacktestConfig, run_backtest
from .core import Portfolio, RiskEngine, RiskConfig
from .strategies import Candle

app = FastAPI(title="AlgoDesk Trader", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
market_client = BinancePublicClient()


class RuntimeStatus(BaseModel):
    mode: Literal["backtest", "paper", "testnet", "live"]
    live_trading_enabled: bool
    broker: str
    trading_enabled: bool


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "trader"}


@app.get("/ready", response_model=RuntimeStatus)
def ready() -> RuntimeStatus:
    mode = os.getenv("TRADING_MODE", "paper").lower()
    live_enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    return RuntimeStatus(
        mode=mode if mode in {"backtest", "paper", "testnet", "live"} else "paper",
        live_trading_enabled=live_enabled,
        broker="paper" if mode == "paper" else "binance-spot",
        trading_enabled=mode in {"paper", "testnet"} or (mode == "live" and live_enabled),
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


@app.get("/api/market/ticker")
def market_ticker(response: Response, symbol: str = "BTCUSDT,ETHUSDT") -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    symbols = [value.strip() for value in symbol.split(",") if value.strip()]
    tickers = market_client.ticker_price(symbols[:5])
    return {"source": "binance-public-spot", "tickers": [ticker.__dict__ for ticker in tickers]}


@app.get("/api/backtests/demo")
def demo_backtest() -> dict[str, object]:
    closes = [100 - (index * 0.25) for index in range(35)]
    closes += [91.25 + (index * 0.55) + ((index % 5) * 0.08) for index in range(45)]
    closes += [116 - (index * 0.5) + ((index % 4) * 0.06) for index in range(40)]
    candles = [Candle(index, close - 0.5, close + 1.4, close - 1.2, close, 1000) for index, close in enumerate(closes)]
    result, trades = run_backtest(candles, BacktestConfig(fast_period=8, slow_period=21, position_percent=10))
    return {"mode": "backtest", "symbol": "DEMOUSDT", "metrics": result.__dict__, "trades": len(trades)}
