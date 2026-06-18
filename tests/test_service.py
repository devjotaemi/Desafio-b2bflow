"""Testes da orquestração de disparo: mensagem exata, idempotência, opt-out e dry-run."""

from unittest.mock import MagicMock

from dispatch.config import Settings
from dispatch.models import Contact
from dispatch.service import MESSAGE_TEMPLATE, build_default_message, run_dispatch


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "supabase_url": "u",
        "supabase_key": "k",
        "zapi_instance_id": "i",
        "zapi_instance_token": "t",
        "zapi_client_token": "c",
        "dispatch_rate_limit_seconds": 0,
        "dispatch_max_contacts": 10,
    }
    base.update(overrides)
    return Settings(**base)


def no_sleep(_seconds: float) -> None:
    """sleep no-op para os testes não esperarem o rate limit."""


def test_message_template_is_exact() -> None:
    # Guarda a spec literal: sem vírgula após o nome, com '?' no fim.
    assert MESSAGE_TEMPLATE == "Olá, {nome} tudo bem com você?"
    contact = Contact(id="1", nome_contato="João", telefone="5511999999999")
    assert build_default_message(contact) == "Olá, João tudo bem com você?"


def test_sends_to_eligible_contact() -> None:
    repo = MagicMock()
    repo.get_contacts.return_value = [Contact(id="1", nome_contato="Ana", telefone="11987654321")]
    repo.already_sent.return_value = False
    repo.create_dispatch_record.return_value = "rec"
    zapi = MagicMock()
    zapi.send_text.return_value = "ZID"

    results = run_dispatch(repo, zapi, make_settings(), sleep=no_sleep)

    zapi.send_text.assert_called_once_with("5511987654321", "Olá, Ana tudo bem com você?")
    repo.mark_sent.assert_called_once_with("rec", "ZID")
    assert results[0]["status"] == "sent"


def test_idempotency_skips_already_sent() -> None:
    repo = MagicMock()
    repo.get_contacts.return_value = [Contact(id="1", nome_contato="Ana", telefone="11987654321")]
    repo.already_sent.return_value = True
    zapi = MagicMock()

    results = run_dispatch(repo, zapi, make_settings(), sleep=no_sleep)

    zapi.send_text.assert_not_called()
    repo.create_dispatch_record.assert_not_called()
    assert results[0]["status"] == "skipped_already_sent"


def test_opt_out_contact_is_skipped() -> None:
    repo = MagicMock()
    repo.get_contacts.return_value = [
        Contact(id="1", nome_contato="Ana", telefone="11987654321", opt_out=True)
    ]
    repo.already_sent.return_value = False
    zapi = MagicMock()

    results = run_dispatch(repo, zapi, make_settings(), sleep=no_sleep)

    zapi.send_text.assert_not_called()
    assert results[0]["status"] == "skipped_opt_out"


def test_dry_run_does_not_call_zapi_or_write() -> None:
    repo = MagicMock()
    repo.get_contacts.return_value = [Contact(id="1", nome_contato="Ana", telefone="11987654321")]
    repo.already_sent.return_value = False
    zapi = MagicMock()

    results = run_dispatch(repo, zapi, make_settings(), dry_run=True, sleep=no_sleep)

    zapi.send_text.assert_not_called()
    repo.create_dispatch_record.assert_not_called()
    assert results[0]["status"] == "dry_run"


def test_failed_send_is_marked_and_batch_continues() -> None:
    repo = MagicMock()
    repo.get_contacts.return_value = [
        Contact(id="1", nome_contato="Ana", telefone="11987654321"),
        Contact(id="2", nome_contato="Bia", telefone="11987654322"),
    ]
    repo.already_sent.return_value = False
    repo.create_dispatch_record.side_effect = ["rec1", "rec2"]
    zapi = MagicMock()
    zapi.send_text.side_effect = [RuntimeError("boom"), "ZID2"]

    results = run_dispatch(repo, zapi, make_settings(), sleep=no_sleep)

    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "sent"
    repo.mark_failed.assert_called_once()
    assert zapi.send_text.call_count == 2
