"""Load the versioned, non-secret YAML controls used by PAPER and Testnet."""

from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

import yaml

from .core import RiskConfig
from .paper_engine import PaperEngineConfig
from .settings import settings


def _yaml_mapping(path: str) -> Mapping[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    with file_path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"configuration at {file_path} must be a YAML mapping")
    return payload


def risk_config_from_yaml(path: str = settings.risk_config_path) -> RiskConfig:
    payload = _yaml_mapping(path).get("risk", {})
    if not isinstance(payload, Mapping):
        raise ValueError("risk configuration must be a mapping")
    allowed = {field.name for field in fields(RiskConfig)}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"unsupported risk configuration: {', '.join(sorted(unknown))}")
    return RiskConfig(**dict(payload))


def paper_engine_config_from_yaml(
    path: str = settings.strategy_config_path,
) -> PaperEngineConfig:
    payload = _yaml_mapping(path).get("strategy", {})
    if not isinstance(payload, Mapping):
        raise ValueError("strategy configuration must be a mapping")
    allowed = {
        "id",
        "type",
        "symbol",
        "interval",
        "enabled",
        "strategy_version",
        "starting_cash",
        "position_percent",
        "fee_bps",
        "fast_ema",
        "slow_ema",
        "atr_period",
        "stop_loss_atr",
        "take_profit_atr",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"unsupported strategy configuration: {', '.join(sorted(unknown))}")
    if str(payload.get("type", "ema_trend")).lower() != "ema_trend":
        raise ValueError("only ema_trend is enabled in this release")
    mapped = {
        "strategy_id": payload.get("id", PaperEngineConfig.strategy_id),
        "strategy_version": payload.get("strategy_version", PaperEngineConfig.strategy_version),
        "symbol": payload.get("symbol", PaperEngineConfig.symbol),
        "interval": payload.get("interval", PaperEngineConfig.interval),
        "starting_cash": payload.get("starting_cash", PaperEngineConfig.starting_cash),
        "position_percent": payload.get("position_percent", PaperEngineConfig.position_percent),
        "fee_bps": payload.get("fee_bps", PaperEngineConfig.fee_bps),
        "fast_period": payload.get("fast_ema", PaperEngineConfig.fast_period),
        "slow_period": payload.get("slow_ema", PaperEngineConfig.slow_period),
        "atr_period": payload.get("atr_period", PaperEngineConfig.atr_period),
        "stop_loss_atr": payload.get("stop_loss_atr", PaperEngineConfig.stop_loss_atr),
        "take_profit_atr": payload.get("take_profit_atr", PaperEngineConfig.take_profit_atr),
    }
    if not bool(payload.get("enabled", True)):
        raise ValueError("configured strategy is disabled")
    return PaperEngineConfig(**mapped)
