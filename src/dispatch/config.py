from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supabase_url: str
    supabase_key: str

    zapi_instance_id: str
    zapi_instance_token: str
    zapi_client_token: str
    zapi_base_url: str = "https://api.z-api.io"

    dispatch_rate_limit_seconds: float = 3.0
    dispatch_max_contacts: int = 3
    dry_run: bool = False

    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
