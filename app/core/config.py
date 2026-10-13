"""
Centralised settings loaded from environment / .env file.
Never hardcode secrets — every sensitive value lives here.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ──────────────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    api_key: str = ""  # empty → auth disabled

    # ── Cache ─────────────────────────────────────────────────────────
    cache_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_search: int = 300
    cache_ttl_details: int = 600
    cache_ttl_episodes: int = 300
    cache_ttl_trending: int = 900
    cache_ttl_schedule: int = 3600

    # ── Provider toggles ──────────────────────────────────────────────
    provider_anilist_enabled: bool = True
    provider_jikan_enabled: bool = True
    provider_anikito_enabled: bool = False
    provider_miruro_enabled: bool = False
    provider_anivault_enabled: bool = False
    provider_yumezone_enabled: bool = False

    # ── HTTP ──────────────────────────────────────────────────────────
    http_timeout: float = 10.0
    http_max_retries: int = 3
    http_concurrency_limit: int = 20

    # ── Rate limits ───────────────────────────────────────────────────
    rate_anilist_rpm: int = 90
    rate_jikan_rpm: int = 60

    @field_validator("log_level")
    @classmethod
    def upper_log(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
