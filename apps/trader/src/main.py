"""AlgoDesk trading service seam.

This v0.1 service intentionally exposes health/readiness only. Trading is
disabled until the domain, paper broker, persistence and reconciliation gates
are implemented and tested.
"""
import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from .core import Portfolio, RiskEngine, RiskConfig

app = FastAPI(title="AlgoDesk Trader", version="0.1.0")


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
