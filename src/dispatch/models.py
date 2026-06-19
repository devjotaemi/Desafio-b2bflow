from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    nome_contato: str
    telefone: str
    opt_out: bool = False
    created_at: datetime | None = None


class DispatchRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    contact_id: str | None = None
    telefone: str
    message: str
    status: str = "pending"
    zapi_message_id: str | None = None
    error: str | None = None
    attempts: int = 0
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime | None = None


class ZApiResponse(BaseModel):
    # Resposta do envio de texto da Z-API.

    # A Z-API pode retornar o identificador da mensagem em campos diferentes
    # ("messageId", "zaapId", "id"); "from_api" extrai o primeiro
    # disponível e guarda o payload bruto para auditoria/log.

    message_id: str
    raw: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, object]) -> ZApiResponse:
        for key in ("messageId", "zaapId", "id", "messageID", "message_id"):
            value = data.get(key)
            if value:
                return cls(message_id=str(value), raw=data)
        raise ValueError(f"Resposta da Z-API sem identificador de mensagem: {data!r}")
