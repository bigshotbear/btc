from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/btc_engine"
    raw_data_dir: Path = Path("./data/raw")
    raw_archive_enabled: bool = True

    kalshi_env: Literal["production", "demo"] = "demo"
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: Path | None = None
    kalshi_private_key_pem: str | None = None
    kalshi_series_ticker: str = "KXBTC15M"
    kalshi_discovery_interval_seconds: float = Field(default=15.0, ge=5.0)
    kalshi_enable: bool = True

    coinbase_enable: bool = True
    coinbase_product_id: str = "BTC-USD"
    kraken_enable: bool = True
    kraken_symbol: str = "BTC/USD"
    kraken_book_depth: Literal[10, 25, 100, 500, 1000] = 100

    db_batch_size: int = Field(default=500, ge=1, le=5000)
    db_flush_interval_ms: int = Field(default=250, ge=25, le=5000)
    health_stale_seconds: float = Field(default=5.0, ge=1.0)
    port: int = Field(default=8000, ge=1, le=65535)

    @property
    def kalshi_rest_base(self) -> str:
        if self.kalshi_env == "production":
            return "https://external-api.kalshi.com/trade-api/v2"
        return "https://external-api.demo.kalshi.co/trade-api/v2"

    @property
    def kalshi_ws_url(self) -> str:
        if self.kalshi_env == "production":
            return "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
        return "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

    @property
    def kalshi_private_key_bytes(self) -> bytes:
        if self.kalshi_private_key_pem:
            return self.kalshi_private_key_pem.replace("\\n", "\n").encode()
        if self.kalshi_private_key_path:
            return self.kalshi_private_key_path.read_bytes()
        raise ValueError("Set KALSHI_PRIVATE_KEY_PATH or KALSHI_PRIVATE_KEY_PEM")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Railway commonly provides postgresql://; SQLAlchemy async needs asyncpg.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
