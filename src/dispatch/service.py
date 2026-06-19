# Orquestração do disparo: opt-out, idempotência, rate limit, envio e log.
# A mensagem chega como uma função ("message_provider"), e não hardcoded no
# meio do loop. Hoje devolve a string exata exigida pelo desafio; amanhã o mesmo
# motor pode receber um texto gerado por IA sem tocar nesta lógica.


from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from dispatch.logging import get_logger
from dispatch.models import Contact
from dispatch.phone import InvalidPhoneNumberError, normalize_phone

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger

    from dispatch.config import Settings
    from dispatch.repository import SupabaseRepository
    from dispatch.zapi import ZApiClient

MESSAGE_TEMPLATE = "Olá, {nome} tudo bem com você?"


def build_default_message(contact: Contact) -> str:
    """Mensagem padrão exigida pelo desafio (substitui o nome do contato)."""
    return MESSAGE_TEMPLATE.format(nome=contact.nome_contato)


def run_dispatch(
    repository: SupabaseRepository,
    zapi: ZApiClient,
    settings: Settings,
    *,
    dry_run: bool = False,
    message_provider: Callable[[Contact], str] = build_default_message,
    sleep: Callable[[float], None] = time.sleep,
    logger: FilteringBoundLogger | None = None,
) -> list[dict[str, str]]:
    """Dispara mensagens para os contatos elegíveis e devolve um resumo por contato."""
    log = logger or get_logger()
    contacts = repository.get_contacts(settings.dispatch_max_contacts)
    total = len(contacts)
    log.info("dispatch_started", total=total, dry_run=dry_run)

    results: list[dict[str, str]] = []
    for index, contact in enumerate(contacts):
        clog = log.bind(contact_id=contact.id, nome=contact.nome_contato)

        # não enviar para quem pediu opt-out (defesa extra ao filtro do banco).
        if contact.opt_out:
            clog.info("skip_opt_out")
            results.append({"contact_id": contact.id, "status": "skipped_opt_out"})
            continue

        # não reenviar para quem já recebeu com sucesso.
        if repository.already_sent(contact.id):
            clog.info("skip_already_sent")
            results.append({"contact_id": contact.id, "status": "skipped_already_sent"})
            continue

        try:
            phone = normalize_phone(contact.telefone)
        except InvalidPhoneNumberError as exc:
            clog.warning("invalid_phone", telefone=contact.telefone, error=str(exc))
            results.append({"contact_id": contact.id, "status": "invalid_phone", "error": str(exc)})
            continue

        clog = clog.bind(telefone=phone)
        message = message_provider(contact)

        if dry_run:
            clog.info("dry_run_skip_send", message=message)
            results.append({"contact_id": contact.id, "status": "dry_run", "telefone": phone})
            continue

        record_id = repository.create_dispatch_record(contact.id, phone, message)
        try:
            message_id = zapi.send_text(phone, message)
        except Exception as exc:
            repository.mark_failed(record_id, str(exc))
            clog.error("send_failed", error=str(exc))
            results.append({"contact_id": contact.id, "status": "failed", "error": str(exc)})
        else:
            repository.mark_sent(record_id, message_id)
            clog.info("send_ok", zapi_message_id=message_id)
            results.append(
                {"contact_id": contact.id, "status": "sent", "zapi_message_id": message_id}
            )

        # anti-ban: aguarda entre envios reais.
        if index < total - 1:
            sleep(settings.dispatch_rate_limit_seconds)

    log.info("dispatch_finished", total=total, results=results)
    return results
