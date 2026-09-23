-- 005 — Prospección: base de PyMEs de Querétaro (DENUE + directorios).
-- Es el UNIVERSO: prioriza a quién contactar. El seguimiento vive en el CRM
-- (prospectos/interacciones de la 004): "Pasar al CRM" llena prospecto_id.
-- Estas tablas NO se cargan a memoria (son miles de filas): el módulo
-- app/prospeccion las consulta con su propia conexión.

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

-- Los prospectos que vienen de esta base llevan origen 'denue'.
alter table prospectos drop constraint if exists prospectos_origen_check;
alter table prospectos add constraint prospectos_origen_check
    check (origen in ('canacintra','referido','linkedin','campo','llamada_alex','denue','otro'));

alter table pq_empresas         enable row level security;
alter table pq_establecimientos enable row level security;
alter table pq_contactos        enable row level security;
alter table pq_directorio       enable row level security;
alter table pq_consumo_api      enable row level security;
insert into migraciones (numero, nombre) values (5, 'prospección: base PyMEs Querétaro') on conflict do nothing;
