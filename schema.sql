-- =============================================================
-- Comando PM — esquema de base de datos (Supabase / Postgres)
-- Fuente de verdad de la DB. Migración inicial: 001
-- =============================================================

-- ---------- Enums ----------
create type estado_proyecto as enum ('activo', 'pausado', 'cerrado', 'cancelado');
create type estado_tarea    as enum ('pendiente', 'en_curso', 'hecha', 'bloqueada');
create type tipo_reto       as enum ('riesgo', 'bloqueo', 'decision_pendiente');
create type estado_reto     as enum ('abierto', 'mitigado', 'materializado', 'cerrado');
create type tipo_documento  as enum ('charter', 'canvas', 'porter', 'roadmap', 'rca');

-- ---------- Proyectos ----------
-- La salud (verde/amarillo/rojo) NO se guarda: se calcula siempre
-- en el dominio a partir de tareas, retos y SPI.
create table proyectos (
    id                 uuid primary key default gen_random_uuid(),
    nombre             text not null,
    descripcion        text default '',
    estado             estado_proyecto not null default 'activo',
    fecha_inicio       date not null,
    fecha_fin_objetivo date not null,
    color              text not null default '#4f46e5', -- chip visual en la UI
    prioridad          int  not null default 3,          -- 1 (alta) a 5 (baja)
    fase               text default '',                  -- anotación de roadmap: "Descubrimiento", etc.
    fase_inicio        date,
    fase_fin           date,
    lecciones          text default '',                  -- se llena al cerrar el proyecto
    creado_en          timestamptz not null default now(),
    actualizado_en     timestamptz not null default now()
);

-- ---------- Objetivos SMART ----------
create table objetivos (
    id             uuid primary key default gen_random_uuid(),
    proyecto_id    uuid not null references proyectos(id) on delete cascade,
    especifico     text not null,           -- S: qué exactamente
    metrica        text not null,           -- M: nombre de la métrica
    valor_objetivo numeric not null,        -- M: meta numérica (validación dura)
    valor_actual   numeric not null default 0,
    alcanzable     text not null,           -- A: justificación
    relevante      text not null,           -- R: justificación
    fecha_limite   date not null,           -- T
    creado_en      timestamptz not null default now()
);

-- ---------- Tareas (incluye hitos: es_hito = true, duración 0) ----------
create table tareas (
    id                  uuid primary key default gen_random_uuid(),
    proyecto_id         uuid not null references proyectos(id) on delete cascade,
    titulo              text not null,
    descripcion         text default '',
    estado              estado_tarea not null default 'pendiente',
    fecha_inicio        date not null,
    fecha_fin           date not null,
    es_hito             boolean not null default false,
    importante          boolean not null default false,
    urgente_manual      boolean,             -- null = urgencia automática por fecha
    dependencias        uuid[] not null default '{}',
    esfuerzo_estimado_h numeric not null default 1,
    esfuerzo_real_h     numeric,
    origen_rca          uuid,                -- si nació de una acción correctiva de un RCA
    creado_en           timestamptz not null default now(),
    actualizado_en      timestamptz not null default now(),
    check (fecha_fin >= fecha_inicio),
    check (not es_hito or fecha_inicio = fecha_fin) -- un hito dura 0 días
);

create index idx_tareas_proyecto on tareas (proyecto_id, estado);
create index idx_tareas_fechas   on tareas (fecha_fin) where estado <> 'hecha';

-- ---------- Retos (riesgos / bloqueos / decisiones) ----------
create table retos (
    id                uuid primary key default gen_random_uuid(),
    proyecto_id       uuid not null references proyectos(id) on delete cascade,
    titulo            text not null,
    tipo              tipo_reto not null default 'riesgo',
    impacto           int not null check (impacto between 1 and 5),
    probabilidad      int not null check (probabilidad between 1 and 5),
    plan_de_respuesta text default '',
    estado            estado_reto not null default 'abierto',
    creado_en         timestamptz not null default now(),
    actualizado_en    timestamptz not null default now()
);

create index idx_retos_abiertos on retos (proyecto_id) where estado = 'abierto';

-- ---------- Documentos estratégicos (JSONB versionado) ----------
create table documentos (
    id          uuid primary key default gen_random_uuid(),
    proyecto_id uuid references proyectos(id) on delete cascade, -- null = nivel portafolio (ej. Porter)
    tipo        tipo_documento not null,
    version     int not null default 1,
    contenido   jsonb not null default '{}',
    creado_en   timestamptz not null default now()
);

create index idx_documentos on documentos (proyecto_id, tipo, version desc);

-- ---------- Plan del día (método Ivy Lee: máx. 6 tareas ordenadas) ----------
create table planes_dia (
    fecha        date primary key,
    tarea_ids    uuid[] not null default '{}',  -- orden = prioridad; el dominio valida máx. 6
    cerrado      boolean not null default false,
    nota_cierre  text default '',
    creado_en    timestamptz not null default now()
);

-- ---------- Snapshots diarios de KPIs (para gráficas de tendencia) ----------
create table kpi_snapshots (
    proyecto_id     uuid not null references proyectos(id) on delete cascade,
    fecha           date not null,
    avance_pct      numeric not null,
    spi             numeric not null,
    tareas_vencidas int not null,
    retos_abiertos  int not null,
    salud           text not null, -- 'verde' | 'amarillo' | 'rojo' (foto histórica, sí se guarda)
    primary key (proyecto_id, fecha)
);

-- ---------- Trigger de actualizado_en ----------
create or replace function marcar_actualizado() returns trigger as $$
begin
    new.actualizado_en = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_proyectos_act before update on proyectos
    for each row execute function marcar_actualizado();
create trigger trg_tareas_act before update on tareas
    for each row execute function marcar_actualizado();
create trigger trg_retos_act before update on retos
    for each row execute function marcar_actualizado();
