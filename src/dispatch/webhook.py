"""Receiver FastAPI dos callbacks de status da Z-API (enviada/entregue/lida).

A Z-API envia callbacks para uma URL pública configurada no painel. Aqui
correlacionamos o callback ao ``dispatch_log`` pelo ``zapi_message_id`` e
atualizamos status + timestamps. Os nomes de campos seguem o contrato conhecido
da Z-API; confirme na doc oficial antes de produção.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from dispatch.config import get_settings
from dispatch.logging import get_logger

if TYPE_CHECKING:
    from dispatch.repository import SupabaseRepository

log = get_logger()

# Mapeia os status da Z-API para os status internos do dispatch_log.
_STATUS_MAP = {
    "SENT": "sent",
    "RECEIVED": "delivered",
    "DELIVERED": "delivered",
    "READ": "read",
    "READ-SELF": "read",
    "PLAYED": "read",
}


def _extract_message_id(payload: dict[str, Any]) -> str | None:
    for key in ("messageId", "zaapId", "id", "messageID"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def create_app(repository: SupabaseRepository | None = None) -> FastAPI:
    app = FastAPI(title="b2bflow dispatch webhook", version="0.1.0")
    state: dict[str, SupabaseRepository | None] = {"repository": repository}

    def get_repository() -> SupabaseRepository:
        if state["repository"] is None:
            from dispatch.repository import SupabaseRepository

            settings = get_settings()
            state["repository"] = SupabaseRepository(settings.supabase_url, settings.supabase_key)
        return state["repository"]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook/status")
    def webhook_status(payload: dict[str, Any]) -> dict[str, Any]:
        message_id = _extract_message_id(payload)
        raw_status = str(payload.get("status", "")).upper()
        status = _STATUS_MAP.get(raw_status)
        clog = log.bind(zapi_message_id=message_id, raw_status=raw_status)

        if not message_id or status is None:
            clog.warning("webhook_ignored")
            return {"updated": 0, "ignored": True}

        updated = get_repository().update_status_by_zapi_id(message_id, status)
        clog.info("webhook_status_updated", status=status, updated=updated)
        return {"updated": updated, "status": status}

    return app
