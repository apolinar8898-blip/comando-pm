-- =============================================================
-- Comando PM — esquema de base de datos (Supabase / Postgres)
-- Fuente de verdad de la DB: estado COMPLETO actual (001 + 002 + 003…).
-- Para una DB nueva corre este archivo; para una existente, solo las
-- migraciones pendientes de migraciones/ (tabla "migraciones" dice cuáles).
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

-- ---------- Rutinas (trabajo recurrente → una tarea real por día) ----------
create table rutinas (
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

alter table tareas add column rutina_id uuid references rutinas(id) on delete set null;
create index idx_tareas_rutina on tareas (rutina_id, fecha_fin);

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
    historial   jsonb not null default '[]',  -- [{version, contenido, fecha}]
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

-- ---------- Seguridad: cerrar la API pública de Supabase (PostgREST) ----------
-- El backend entra como 'postgres' (no le afecta RLS); la llave anon no lee nada.
alter table proyectos     enable row level security;
alter table objetivos     enable row level security;
alter table tareas        enable row level security;
alter table retos         enable row level security;
alter table documentos    enable row level security;
alter table planes_dia    enable row level security;
alter table kpi_snapshots enable row level security;
alter table rutinas       enable row level security;

-- ---------- Captación SINPROTEK (Fase 1) ----------
create table if not exists prospectos (
    id                   uuid primary key default gen_random_uuid(),
    empresa              text not null,
    contacto             text default '',
    puesto               text default '',
    telefono             text default '',
    correo               text default '',
    giro                 text default '',
    origen               text not null default 'otro'
        check (origen in ('canacintra','referido','linkedin','campo','llamada_alex','denue','otro')),
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

-- ---------- Prospección: base de PyMEs de Querétaro (migración 005) ----------
-- Universo de empresas del DENUE; el seguimiento vive en prospectos (CRM).
create table if not exists pq_empresas (
    empresa_id           text primary key,              -- "denue:<id del establecimiento representativo>"
    nombre_comercial     text not null,
    razon_social         text default '',
    dominio              text default '',                -- propio; nunca gmail/hotmail…
    sitio_web            text default '',
    scian_codigo         text not null,
    scian_nombre         text not null,
    sector               text not null,                  -- 2 dígitos SCIAN
    estrato              text not null,                  -- per_ocu del DENUE ("11 a 30 personas")
    segmento             text not null check (segmento in ('nucleo','micro_plus')),
    es_asociacion        boolean not null default false, -- SCIAN 813: se marca, no se excluye
    cve_mun              text not null,
    municipio            text not null,
    num_establecimientos int not null default 1,
    telefono_principal   text default '',                -- E.164 (+52…)
    fuente_telefono      text default '',
    parece_celular       boolean,                        -- null = no se sabe (ver IDEAS.md)
    whatsapp_detectado   boolean not null default false,
    correo_generico      text default '',
    fuente_correo        text default '',
    afiliado_canacintra  boolean not null default false,
    directorios          text[] not null default '{}',   -- p. ej. {piq_2024}
    score_fit            int,
    score_detalle        jsonb not null default '{}',
    tier                 text check (tier in ('A','B','C')),
    resumen_negocio      text default '',
    prospecto_id         uuid references prospectos(id) on delete set null,
    opt_out              boolean not null default false,
    vigente              boolean not null default true,  -- false = ya no aparece en el DENUE
    edicion_denue        text default '',
    creado               timestamptz not null default now(),
    actualizado          timestamptz not null default now()
);
create index if not exists idx_pq_empresas_tier on pq_empresas (tier, score_fit desc);
create index if not exists idx_pq_empresas_mun  on pq_empresas (cve_mun);
create index if not exists idx_pq_empresas_tel  on pq_empresas (telefono_principal);

create table if not exists pq_establecimientos (
    establecimiento_id text primary key,                 -- id del DENUE
    empresa_id         text not null references pq_empresas(empresa_id),
    clee               text default '',
    nom_estab          text not null,
    raz_social         text default '',
    scian_codigo       text not null,
    per_ocu            text not null,
    telefono_e164      text default '',
    correo             text default '',
    www                text default '',
    direccion          text default '',
    colonia            text default '',
    cod_postal         text default '',
    cve_mun            text not null,
    municipio          text not null,
    localidad          text default '',
    latitud            numeric,
    longitud           numeric,
    fecha_alta         text default '',                  -- "2019-11" tal cual lo da el DENUE
    vigente            boolean not null default true,
    edicion_denue      text default '',
    actualizado        timestamptz not null default now()
);
create index if not exists idx_pq_estab_empresa on pq_establecimientos (empresa_id);

create table if not exists pq_contactos (
    id              uuid primary key default gen_random_uuid(),
    empresa_id      text not null references pq_empresas(empresa_id),
    nombre          text default '',
    puesto          text default '',
    telefono        text default '',
    correo          text default '',
    fuente_contacto text not null check (fuente_contacto in ('denue','web','apollo','manual','directorio')),
    verificado      boolean not null default false,
    opt_out         boolean not null default false,
    creado          timestamptz not null default now()
);
create index if not exists idx_pq_contactos_empresa on pq_contactos (empresa_id);

-- Directorios externos (PIQ, CANACINTRA…) y su cruce con el DENUE.
-- estado 'pendiente' = cola de revisión manual (match dudoso).
create table if not exists pq_directorio (
    id          bigserial primary key,
    fuente      text not null,                           -- 'piq_2024', 'canacintra'…
    nombre      text not null,
    giro        text default '',
    telefono    text default '',                         -- E.164
    direccion   text default '',
    datos       jsonb not null default '{}',             -- columnas originales
    empresa_id  text references pq_empresas(empresa_id),
    confianza   numeric,                                 -- 0–100
    metodo      text default '',                         -- 'telefono' | 'nombre'
    estado      text not null default 'pendiente'
        check (estado in ('empatado','pendiente','sin_match','descartado')),
    creado      timestamptz not null default now(),
    unique (fuente, nombre)
);

create table if not exists pq_consumo_api (
    id        bigserial primary key,
    proveedor text not null check (proveedor in ('tavily','apollo','inegi')),
    creditos  numeric not null check (creditos >= 0),
    fecha     timestamptz not null default now(),
    lote      text default '',
    detalle   text default ''
);
create index if not exists idx_pq_consumo on pq_consumo_api (proveedor, fecha);

alter table pq_empresas         enable row level security;
alter table pq_establecimientos enable row level security;
alter table pq_contactos        enable row level security;
alter table pq_directorio       enable row level security;
alter table pq_consumo_api      enable row level security;

-- ---------- Registro de migraciones aplicadas ----------
create table migraciones (
    numero   int primary key,
    nombre   text not null,
    aplicada timestamptz not null default now()
);
alter table migraciones enable row level security;
insert into migraciones (numero, nombre) values
    (1, 'schema inicial'), (2, 'fase0: historial documentos + RLS'), (3, 'rutinas'),
    (4, 'fase1: captación'), (5, 'prospección: base PyMEs Querétaro');
