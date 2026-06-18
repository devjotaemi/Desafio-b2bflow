"""Acesso ao Supabase: leitura de contatos e escrita/atualização do log de disparo.

Concentra toda a conversa com o banco aqui para manter o ``service`` agnóstico
de persistência (e fácil de testar com um repositório fake).
"""

from __future__ import annotations

from datetime import UTC, datetime

from supabase import Client, create_client

from dispatch.models import Contact

# Status que indicam que o contato já recebeu a mensagem com sucesso.
_SENT_STATUSES = ("sent", "delivered", "read")


class SupabaseRepository:
    """Repositório de contatos e log de disparo sobre o Supabase."""

    def __init__(self, url: str, key: str, *, client: Client | None = None) -> None:
        self._client = client or create_client(url, key)

    def get_contacts(self, limit: int) -> list[Contact]:
        """Retorna contatos elegíveis (``opt_out = false``), mais antigos primeiro."""
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
        """True se já existe um disparo bem-sucedido para o contato (idempotência)."""
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
        """Cria o registro ``pending`` e devolve seu id."""
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
        """Marca o registro como ``sent`` e guarda o id da Z-API para o webhook."""
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
        """Marca o registro como ``failed`` com a mensagem de erro."""
        (
            self._client.table("dispatch_log")
            .update({"status": "failed", "error": error, "attempts": 1})
            .eq("id", record_id)
            .execute()
        )

    def update_status_by_zapi_id(
        self, zapi_message_id: str, status: str, *, timestamp: datetime | None = None
    ) -> int:
        """Atualiza status/timestamps a partir do callback do webhook.

        Localiza o registro pelo ``zapi_message_id`` e devolve quantas linhas
        foram afetadas (0 se o id não for encontrado).
        """
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
