"""Typed runtime configuration with safe defaults for local PAPER mode."""
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


_path = Path(__file__).resolve()
_candidates = [_path.parents[index] for index in (3, 1) if index < len(_path.parents)]
PROJECT_ROOT = next((candidate for candidate in _candidates if (candidate / "data").exists() or (candidate / ".env").exists()), _path.parents[1])
LOCAL_ENV = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(LOCAL_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    trading_mode: Literal["backtest", "paper", "testnet", "live"] = "paper"
    live_trading_enabled: bool = False
    binance_api_key: str = ""
    binance_api_secret: SecretStr = SecretStr("")
    binance_testnet: bool = False
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'algodesk.db').as_posix()}"
    api_port: int = 8000
    binance_api_base_url: str = "https://api.binance.com"
    binance_ws_base_url: str = "wss://stream.binance.com:9443/stream"
    allowed_origins: str = "http://localhost:4173,http://127.0.0.1:4173"

    @property
    def account_configured(self) -> bool:
        return bool(self.binance_api_key.strip() and self.binance_api_secret.get_secret_value().strip())

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
