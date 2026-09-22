-- 003 — Rutinas: trabajo recurrente que genera una tarea real por día
create table if not exists rutinas (
    id                  uuid primary key default gen_random_uuid(),
    proyecto_id         uuid not null references proyectos(id) on delete cascade,
    titulo              text not null,
    dias_semana         int[] not null,            -- 0 = lunes … 6 = domingo
    importante          boolean not null default true,
    esfuerzo_estimado_h numeric not null default 1,
    desde               date not null,
    hasta               date,
    activa              boolean not null default true,
    generada_hasta      date,                      -- último día ya materializado
    creado_en           timestamptz not null default now(),
    check (cardinality(dias_semana) >= 1 and dias_semana <@ array[0,1,2,3,4,5,6]),
    check (hasta is null or hasta >= desde)
);
alter table rutinas enable row level security;

alter table tareas add column if not exists rutina_id uuid references rutinas(id) on delete set null;
create index if not exists idx_tareas_rutina on tareas (rutina_id, fecha_fin);

insert into migraciones (numero, nombre) values (3, 'rutinas') on conflict do nothing;
