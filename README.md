# b2bflow — Motor de Disparo de WhatsApp

[![CI](https://github.com/devjotaemi/Desafio-b2bflow/actions/workflows/ci.yml/badge.svg)](https://github.com/devjotaemi/Desafio-b2bflow/actions/workflows/ci.yml)

Lê contatos cadastrados no **Supabase** e dispara, via **Z-API**, uma mensagem de
WhatsApp para até 3 números. O ponto central é a **filosofia**: isto não é um script
descartável, e sim a **semente de um motor de disparo** — pensado como o produto real
precisaria. Por isso há log auditável, idempotência, conformidade com a LGPD (opt-out),
rastreamento de status de entrega/leitura e resistência a banimento (rate limit), sem
cair em over-engineering.

---

## Stack

- **Python 3.12+** com **[uv](https://docs.astral.sh/uv/)** (deps + venv reproduzíveis)
- **httpx** (cliente HTTP) + **tenacity** (retry/backoff)
- **pydantic-settings** (config tipada do `.env`, fail-fast)
- **phonenumbers** (normalização E.164) · **structlog** (logs JSON)
- **supabase-py** (banco) · **typer** (CLI) · **fastapi + uvicorn** (webhook)
- **pytest + respx** (testes, Z-API mockada) · **ruff** (lint/format) · **GitHub Actions** (CI)

---

## 1. Setup da tabela (Supabase / Postgres)

Crie as tabelas executando o conteúdo de [`sql/schema.sql`](sql/schema.sql) no
**SQL Editor** do Supabase:

```sql
-- Contatos a serem disparados
create table if not exists contatos (
  id uuid primary key default gen_random_uuid(),
  nome_contato text not null,
  telefone text not null,                         -- idealmente já em E.164 (ex: 5517999999999)
  opt_out boolean not null default false,         -- LGPD: quem pediu para não receber
  created_at timestamptz not null default now()
);

-- Log de disparo: auditoria + idempotência + tracking de status
create table if not exists dispatch_log (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contatos(id),
  telefone text not null,
  message text not null,
  status text not null default 'pending',         -- pending | sent | failed | delivered | read
  zapi_message_id text,                           -- correlaciona o callback do webhook
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

### Popule contatos de teste

Use **seus próprios números** (com você no WhatsApp), em `DDI+DDD+número`:

```sql
insert into contatos (nome_contato, telefone) values
  ('Maria', '5517999999999'),
  ('João',  '5511988888888'),
  ('Ana',   '5521977777777');
```

> Para testar o opt-out (LGPD), marque um contato com `opt_out = true` e confirme
> que ele é ignorado no disparo.

---

## 2. Variáveis de ambiente

Copie o template e preencha com suas credenciais:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `SUPABASE_URL` | ✅ | — | URL do projeto Supabase |
| `SUPABASE_KEY` | ✅ | — | **service role key** (uso server-side; nunca expor no client) |
| `ZAPI_INSTANCE_ID` | ✅ | — | ID da instância na Z-API |
| `ZAPI_INSTANCE_TOKEN` | ✅ | — | Token da instância na Z-API |
| `ZAPI_CLIENT_TOKEN` | ✅ | — | **Token de Segurança da Conta** (header `Client-Token`) |
| `ZAPI_BASE_URL` | — | `https://api.z-api.io` | Base da API Z-API |
| `DISPATCH_RATE_LIMIT_SECONDS` | — | `3` | Delay entre envios (anti-ban) |
| `DISPATCH_MAX_CONTACTS` | — | `3` | Teto de contatos por execução |
| `DRY_RUN` | — | `false` | `true` = simula, não chama a Z-API |
| `WEBHOOK_HOST` | — | `0.0.0.0` | Host do receiver de webhook |
| `WEBHOOK_PORT` | — | `8000` | Porta do receiver de webhook |
| `LOG_LEVEL` | — | `INFO` | Nível de log (structlog) |

A configuração é validada na inicialização: se faltar uma variável obrigatória, o
programa falha imediatamente com uma mensagem clara (fail-fast), em vez de quebrar no
meio de um disparo.

---

## 3. Como rodar

Instale as dependências (cria o `.venv` a partir do `uv.lock`):

```bash
uv sync
```

Dispara o fluxo principal de ponta a ponta:

```bash
python main.py            # com o .venv ativo
# ou, sem ativar o ambiente:
uv run python main.py
```

Simula sem chamar a Z-API (nenhuma mensagem é enviada, nada é gravado):

```bash
uv run python main.py --dry-run
```

Comandos extras da CLI:

```bash
uv run dispatch validate   # testa conexões com Supabase e Z-API (sem enviar)
uv run dispatch webhook    # sobe o receiver FastAPI de status
uv run dispatch dispatch --dry-run   # equivalente ao main.py --dry-run
```

Rodar lint e testes localmente (o mesmo que a CI executa):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

---

## 4. Como configurar o webhook (status de entrega/leitura)

A Z-API envia callbacks de status (`SENT`, `DELIVERED`, `READ`, …) para uma **URL
pública**. O receiver atualiza o `dispatch_log` correlacionando pelo `zapi_message_id`.

1. Suba o receiver: `uv run dispatch webhook` (porta `8000` por padrão).
2. Exponha-o publicamente. Em desenvolvimento, o mais simples é o **ngrok**:
   ```bash
   ngrok http 8000
   ```
   Em produção, hospede em uma VPS própria com a porta exposta.
3. No painel da Z-API, configure a URL de webhook de status apontando para
   `https://SEU-DOMINIO/webhook/status`.
4. Verifique a saúde com `GET https://SEU-DOMINIO/health` → `{"status":"ok"}`.

> Usar ngrok/VPS para expor o webhook **não fere** a regra de "plano gratuito" — essa
> regra se aplica a Python, Supabase e Z-API, todos em plano free.

---

## 5. Decisões de arquitetura

- **Log auditável + idempotência** — cada disparo vira uma linha em `dispatch_log`. Antes
  de enviar, o serviço checa se o contato já recebeu com sucesso (`already_sent`) e pula,
  evitando spam e reenvios em reexecuções.
- **LGPD / opt-out** — contatos com `opt_out = true` nunca são contatados. O filtro é
  aplicado no banco **e** reforçado no serviço (defesa em profundidade).
- **Resistência a banimento** — envios respeitam `DISPATCH_RATE_LIMIT_SECONDS` entre
  mensagens; o cliente Z-API re-tenta apenas falhas transitórias (timeout/conexão/5xx) com
  backoff exponencial, e trata 4xx como erro permanente.
- **Tracking de status** — o webhook FastAPI recebe os callbacks e atualiza
  `status`/`delivered_at`/`read_at`, fechando o ciclo de entrega.
- **Gancho de IA (extensibilidade)** — a origem da mensagem é **desacoplada** do envio:
  `run_dispatch` recebe um `message_provider` (hoje a string exata exigida); amanhã o mesmo
  motor receberia um texto gerado por IA sem mudar a orquestração.
- **Confiabilidade desde a config** — `pydantic-settings` valida o `.env` e falha rápido;
  `structlog` produz logs JSON com contexto por contato, prontos para observabilidade.
