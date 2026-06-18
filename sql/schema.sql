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
