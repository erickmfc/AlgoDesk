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
    mapped = {
        "strategy_id": payload.get("id", PaperEngineConfig.strategy_id),
        "symbol": payload.get("symbol", PaperEngineConfig.symbol),
        "fast_period": payload.get("fast_ema", PaperEngineConfig.fast_period),
        "slow_period": payload.get("slow_ema", PaperEngineConfig.slow_period),
    }
    if not bool(payload.get("enabled", True)):
        raise ValueError("configured strategy is disabled")
    return PaperEngineConfig(**mapped)
