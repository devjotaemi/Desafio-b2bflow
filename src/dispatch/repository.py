from __future__ import annotations

from datetime import UTC, datetime

from supabase import Client, create_client

from dispatch.models import Contact

_SENT_STATUSES = ("sent", "delivered", "read")


class SupabaseRepository:
    def __init__(self, url: str, key: str, *, client: Client | None = None) -> None:
        self._client = client or create_client(url, key)

    def get_contacts(self, limit: int) -> list[Contact]:
        response = (
            self._client.table("contatos")
            .select("*")
            .eq("opt_out", False)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return [Contact(**row) for row in response.data]

    def already_sent(self, contact_id: str) -> bool:
        response = (
            self._client.table("dispatch_log")
            .select("id")
            .eq("contact_id", contact_id)
            .in_("status", list(_SENT_STATUSES))
            .limit(1)
            .execute()
        )
        return bool(response.data)

    def create_dispatch_record(self, contact_id: str, telefone: str, message: str) -> str:
        response = (
            self._client.table("dispatch_log")
            .insert(
                {
                    "contact_id": contact_id,
                    "telefone": telefone,
                    "message": message,
                    "status": "pending",
                }
            )
            .execute()
        )
        return response.data[0]["id"]

    def mark_sent(self, record_id: str, zapi_message_id: str) -> None:
        (
            self._client.table("dispatch_log")
            .update(
                {
                    "status": "sent",
                    "zapi_message_id": zapi_message_id,
                    "sent_at": _now_iso(),
                    "attempts": 1,
                }
            )
            .eq("id", record_id)
            .execute()
        )

    def mark_failed(self, record_id: str, error: str) -> None:
        (
            self._client.table("dispatch_log")
            .update({"status": "failed", "error": error, "attempts": 1})
            .eq("id", record_id)
            .execute()
        )

    def update_status_by_zapi_id(
        self, zapi_message_id: str, status: str, *, timestamp: datetime | None = None
    ) -> int:
        ts = (timestamp or datetime.now(UTC)).isoformat()
        update: dict[str, str] = {"status": status}

        if status == "delivered":
            update["delivered_at"] = ts
        elif status == "read":
            update["read_at"] = ts

        response = (
            self._client.table("dispatch_log")
            .update(update)
            .eq("zapi_message_id", zapi_message_id)
            .execute()
        )
        return len(response.data)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
