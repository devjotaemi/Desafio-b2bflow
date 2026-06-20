# b2bflow - Motor de Disparo de WhatsApp

[![CI](https://github.com/devjotaemi/Desafio-b2bflow/actions/workflows/ci.yml/badge.svg)](https://github.com/devjotaemi/Desafio-b2bflow/actions/workflows/ci.yml)

Lê contatos no **Supabase** e dispara, via **Z-API**, uma mensagem de WhatsApp para até 3 números. Mais do que um script: é a **semente de um motor de disparo** com log auditável, idempotência, opt-out (LGPD), rate limit anti-ban e tracking de entrega/leitura.

**Stack:** Python 3.12+ · uv · httpx · tenacity · pydantic-settings · phonenumbers · structlog · supabase · typer · fastapi/uvicorn · pytest+respx · ruff · GitHub Actions.


## Demonstração

[![Demonstração do fluxo no YouTube](https://img.youtube.com/vi/ZAGNoWdRkgs/maxresdefault.jpg)](https://youtu.be/ZAGNoWdRkgs)

Fluxo completo de ponta a ponta: leitura dos contatos no **Supabase** -> envio via **Z-API** -> recebimento no **WhatsApp**. [Assistir no YouTube](https://youtu.be/ZAGNoWdRkgs)

## Setup

**1. Banco** no Supabase (SQL Editor), rode o [`sql/schema.sql`](sql/schema.sql) e popule contatos de teste com **seus números** (DDI+DDD):

```sql
insert into contatos (nome_contato, telefone) values
  ('Maria', '5517999999999');
```

<details><summary>Ver schema (contatos + dispatch_log)</summary>

```sql
create table if not exists contatos (
  id uuid primary key default gen_random_uuid(),
  nome_contato text not null,
  telefone text not null,
  opt_out boolean not null default false,         -- LGPD
  created_at timestamptz not null default now()
);

create table if not exists dispatch_log (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contatos(id),
  telefone text not null,
  message text not null,
  status text not null default 'pending',         -- pending | sent | failed | delivered | read
  zapi_message_id text,                           -- correlaciona o webhook
  error text,
  attempts int not null default 0,
  sent_at timestamptz,
  delivered_at timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_dispatch_log_zapi_message_id on dispatch_log (zapi_message_id);
create index if not exists idx_dispatch_log_contact on dispatch_log (contact_id);
```
</details>

**2. Ambiente** `cp .env.example .env` e preencha:

| Variável | Descrição |
|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` | projeto Supabase + **service role key** (server-side) |
| `ZAPI_INSTANCE_ID` / `ZAPI_INSTANCE_TOKEN` | credenciais da instância Z-API |
| `ZAPI_CLIENT_TOKEN` | Token de Segurança da Conta (header `Client-Token`) |

Opcionais (têm padrão): `ZAPI_BASE_URL`, `DISPATCH_RATE_LIMIT_SECONDS=3`, `DISPATCH_MAX_CONTACTS=3`, `DRY_RUN=false`, `WEBHOOK_HOST`/`WEBHOOK_PORT`, `LOG_LEVEL=INFO`. A config é validada na inicialização (fail-fast).

**3. Dependências** `uv sync`

## Uso

```bash
uv run python main.py            # dispara
uv run python main.py --dry-run  # simula (não chama a Z-API)
uv run dispatch validate         # testa conexões Supabase + Z-API
uv run dispatch webhook          # sobe o receiver de status
uv run pytest                    # testes
```

## Webhook (entrega/leitura)

Suba `uv run dispatch webhook`, exponha a porta 8000 (`ngrok http 8000` ou VPS) e configure a URL `https://SEU-DOMINIO/webhook/status` no painel da Z-API. O receiver correlaciona o callback pelo `zapi_message_id` e atualiza `status`/`delivered_at`/`read_at`.

## Decisões de arquitetura

- **Log + idempotência:** cada envio vira linha em `dispatch_log`; quem já recebeu com sucesso é pulado (sem reenvio).
- **LGPD:** contatos com `opt_out = true` nunca são contatados (filtro no banco + reforço no serviço).
- **Anti-ban:** intervalo entre envios + retry com backoff só em falhas transitórias (timeout/5xx); 4xx é permanente.
- **Tracking:** webhook fecha o ciclo com status de entrega/leitura.
- **Gancho de IA:** a mensagem é injetada via `message_provider` (hoje a string do desafio; amanhã um texto gerado por IA) sem tocar na orquestração.
