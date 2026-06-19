"""CLI (typer) do motor de disparo: ``dispatch``, ``webhook`` e ``validate``."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from dispatch.config import Settings, get_settings
from dispatch.logging import configure_logging, get_logger

app = typer.Typer(add_completion=False, help="Motor de disparo de mensagens da b2bflow.")


def _load_settings() -> Settings:
    """Carrega as configurações ou aborta com mensagem clara (fail-fast)."""
    try:
        return get_settings()
    except ValidationError as exc:
        typer.secho("Configuração inválida — verifique seu .env:", fg=typer.colors.RED, err=True)
        typer.secho(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def dispatch(
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula o disparo sem chamar a Z-API."),
) -> None:
    """Dispara as mensagens para os contatos elegíveis do Supabase."""
    settings = _load_settings()
    configure_logging(settings.log_level)
    effective_dry_run = dry_run or settings.dry_run

    from dispatch.repository import SupabaseRepository
    from dispatch.service import run_dispatch
    from dispatch.zapi import ZApiClient

    repository = SupabaseRepository(settings.supabase_url, settings.supabase_key)
    zapi = ZApiClient(
        settings.zapi_instance_id,
        settings.zapi_instance_token,
        settings.zapi_client_token,
        settings.zapi_base_url,
    )
    try:
        results = run_dispatch(repository, zapi, settings, dry_run=effective_dry_run)
    finally:
        zapi.close()

    sent = sum(1 for r in results if r["status"] == "sent")
    mode = " (dry-run)" if effective_dry_run else ""
    typer.echo(
        f"Disparo concluído{mode}: {len(results)} contato(s) processado(s), {sent} enviado(s)."
    )


@app.command()
def webhook() -> None:
    """Sobe o receiver FastAPI que recebe os callbacks de status da Z-API."""
    settings = _load_settings()
    configure_logging(settings.log_level)

    import uvicorn

    from dispatch.webhook import create_app

    uvicorn.run(create_app(), host=settings.webhook_host, port=settings.webhook_port)


@app.command()
def validate() -> None:
    """Testa as conexões com Supabase e Z-API sem enviar nenhuma mensagem."""
    settings = _load_settings()
    configure_logging(settings.log_level)
    get_logger()

    from dispatch.repository import SupabaseRepository
    from dispatch.zapi import ZApiClient

    ok = True

    try:
        repository = SupabaseRepository(settings.supabase_url, settings.supabase_key)
        contacts = repository.get_contacts(settings.dispatch_max_contacts)
        typer.secho(
            f"Supabase OK — {len(contacts)} contato(s) elegível(is).", fg=typer.colors.GREEN
        )
    except Exception as exc:
        ok = False
        typer.secho(f"Supabase FALHOU: {exc}", fg=typer.colors.RED, err=True)

    zapi = ZApiClient(
        settings.zapi_instance_id,
        settings.zapi_instance_token,
        settings.zapi_client_token,
        settings.zapi_base_url,
    )
    try:
        if zapi.check_connection():
            typer.secho("Z-API OK — instância acessível.", fg=typer.colors.GREEN)
        else:
            ok = False
            typer.secho("Z-API respondeu com erro ao consultar o status.", fg=typer.colors.YELLOW)
    except Exception as exc:
        ok = False
        typer.secho(f"Z-API FALHOU: {exc}", fg=typer.colors.RED, err=True)
    finally:
        zapi.close()

    raise typer.Exit(code=0 if ok else 1)
