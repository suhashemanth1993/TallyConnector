"""Central configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # TallyPrime
    tally_url: str = Field(default="http://localhost:9000")
    tally_timeout_seconds: int = Field(default=15)
    tally_company: str = Field(default="")

    # Frappe cloud ERP
    frappe_base_url: str = Field(default="")
    frappe_api_key: str = Field(default="")
    frappe_api_secret: str = Field(default="")
    frappe_timeout_seconds: int = Field(default=15)

    # Retry engine
    retry_max_attempts: int = Field(default=5)
    retry_backoff_base_seconds: float = Field(default=2.0)

    # Sync
    sync_interval_minutes: int = Field(default=15)
    state_db_path: str = Field(default=".state/sync_state.db")
    frappe_mapping_file: str = Field(default="frappe/mapping.yaml")

    # Logging
    log_level: str = Field(default="INFO")
    debug_mode: bool = Field(default=False)
    log_dir: str = Field(default="logs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
