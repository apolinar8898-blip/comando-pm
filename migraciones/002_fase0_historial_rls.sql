-- 002 — Fase 0: historial de documentos + cerrar la API pública de Supabase
-- (APLICADA el 22/09/2026)
alter table documentos add column if not exists historial jsonb not null default '[]'::jsonb;

-- El backend entra como 'postgres' (no le afecta RLS); la llave anon ya no lee nada.
alter table proyectos     enable row level security;
alter table objetivos     enable row level security;
alter table tareas        enable row level security;
alter table retos         enable row level security;
alter table documentos    enable row level security;
alter table planes_dia    enable row level security;
alter table kpi_snapshots enable row level security;

create table if not exists migraciones (
    numero     int primary key,
    nombre     text not null,
    aplicada   timestamptz not null default now()
);
alter table migraciones enable row level security;
insert into migraciones (numero, nombre) values
    (1, 'schema inicial'), (2, 'fase0: historial documentos + RLS')
on conflict do nothing;
