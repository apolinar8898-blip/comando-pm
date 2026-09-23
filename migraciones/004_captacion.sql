-- 004 — Fase 1: Captación SINPROTEK (CRM de prospectos)
create table if not exists prospectos (
    id                   uuid primary key default gen_random_uuid(),
    empresa              text not null,
    contacto             text default '',
    puesto               text default '',
    telefono             text default '',
    correo               text default '',
    giro                 text default '',
    origen               text not null default 'otro'
        check (origen in ('canacintra','referido','linkedin','campo','llamada_alex','otro')),
    segmento             text not null default 'pyme' check (segmento in ('pyme','independiente')),
    servicio             text not null default 'agente_whatsapp'
        check (servicio in ('agente_whatsapp','agente_voz','consultoria','capacitacion')),
    etapa                text not null default 'identificado'
        check (etapa in ('identificado','contactado','reunion_agendada','demo_hecha',
                         'propuesta_enviada','negociacion','ganado','perdido')),
    fechas_etapa         jsonb not null default '{}',   -- {"contactado": "2026-09-23", …}
    fecha_proxima_accion date,
    proxima_accion       text default '',
    monto_desarrollo     numeric not null default 0 check (monto_desarrollo >= 0),
    monto_mensual        numeric not null default 0 check (monto_mensual >= 0),
    motivo_perdida       text default '',
    link_drive           text default '',
    notas                text default '',
    creado               timestamptz not null default now(),
    actualizado          timestamptz not null default now(),
    check (etapa <> 'perdido' or length(trim(motivo_perdida)) > 0)  -- motivo obligatorio
);
create index if not exists idx_prospectos_etapa on prospectos (etapa);

create table if not exists interacciones (
    id           uuid primary key default gen_random_uuid(),
    prospecto_id uuid not null references prospectos(id) on delete cascade,
    fecha        timestamptz not null default now(),
    canal        text not null check (canal in ('llamada','whatsapp','visita','correo','reunion','alex')),
    resultado    text not null default '',
    nota         text default ''
);
create index if not exists idx_interacciones on interacciones (prospecto_id, fecha desc);

create table if not exists configuracion (
    clave text primary key,
    valor jsonb not null
);
insert into configuracion (clave, valor) values
    ('meta_interacciones_semana', '25'),
    ('probabilidad_etapa', '{"identificado":0.05,"contactado":0.10,"reunion_agendada":0.20,"demo_hecha":0.35,"propuesta_enviada":0.50,"negociacion":0.70}'),
    ('tope_prospeccion_ivy', '6')
on conflict (clave) do nothing;

alter table tareas add column if not exists prospecto_id uuid references prospectos(id) on delete set null;

alter table prospectos    enable row level security;
alter table interacciones enable row level security;
alter table configuracion enable row level security;
insert into migraciones (numero, nombre) values (4, 'fase1: captación') on conflict do nothing;
