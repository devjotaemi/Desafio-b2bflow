"""Configuração tipada da aplicação, carregada e validada do ``.env``.

Usa ``pydantic-settings`` para falhar rápido (``ValidationError``) já na
inicialização caso uma variável obrigatória esteja ausente ou malformada,
em vez de quebrar silenciosamente no meio de um disparo.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variáveis de ambiente da aplicação.

    Os nomes dos campos mapeiam para as variáveis do ``.env`` de forma
    case-insensitive (ex.: ``supabase_url`` <- ``SUPABASE_URL``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str
    supabase_key: str

    # Z-API
    zapi_instance_id: str
    zapi_instance_token: str
    zapi_client_token: str
    zapi_base_url: str = "https://api.z-api.io"

    # Disparo
    dispatch_rate_limit_seconds: float = 3.0
    dispatch_max_contacts: int = 3
    dry_run: bool = False

    # Webhook
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000

    # Logging
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna as configurações (cacheadas para o processo).

    Levanta ``pydantic.ValidationError`` com mensagem clara se faltar alguma
    variável obrigatória.
    """
    return Settings()  # type: ignore[call-arg]
