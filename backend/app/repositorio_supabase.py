"""Persistencia en Supabase (Postgres) — producción.

Mismo almacén en memoria que el Repositorio JSON (main.py no cambia): al
arrancar se carga todo de la DB; cada guardar() compara contra lo último
persistido y escribe SOLO las filas que cambiaron, en una transacción.

- Si la escritura falla, la memoria conserva los cambios y _persistido no se
  actualiza: el siguiente guardar() reintenta el mismo diff (se autocorrige).
- Conexión nueva por guardar(): Railway es de larga vida y una conexión
  abierta días se cae; con pocas escrituras por minuto el costo es nulo.
- DATABASE_URL debe ser la del "Session pooler" de Supabase (IPv4).
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional
from uuid import UUID

from .modelos import Documento, KpiSnapshot, Objetivo, PlanDia, Proyecto, Reto, Rutina, Tarea
from .reloj import ZONA_DEFECTO, zona
from .repositorio import Repositorio

# ---------- Mapa colección → tabla (orden = orden de inserción por FKs) ----------
# Cada columna lleva su tipo Postgres: todo valor viaja como texto y se castea
# explícitamente, así fechas, enums, uuid[] y jsonb no dependen de adivinanzas.

TABLAS: list[dict[str, Any]] = [
    {
        "coleccion": "proyectos", "tabla": "proyectos", "modelo": Proyecto, "pk": ["id"],
        "columnas": {
            "id": "uuid", "nombre": "text", "descripcion": "text", "estado": "estado_proyecto",
            "fecha_inicio": "date", "fecha_fin_objetivo": "date", "color": "text",
            "prioridad": "int", "fase": "text", "fase_inicio": "date", "fase_fin": "date",
            "lecciones": "text", "creado_en": "timestamptz",
        },
    },
    {
        "coleccion": "rutinas", "tabla": "rutinas", "modelo": Rutina, "pk": ["id"],
        "columnas": {
            "id": "uuid", "proyecto_id": "uuid", "titulo": "text", "dias_semana": "int[]",
            "importante": "boolean", "esfuerzo_estimado_h": "numeric", "desde": "date",
            "hasta": "date", "activa": "boolean", "generada_hasta": "date",
        },
    },
    {
        "coleccion": "objetivos", "tabla": "objetivos", "modelo": Objetivo, "pk": ["id"],
        "columnas": {
            "id": "uuid", "proyecto_id": "uuid", "especifico": "text", "metrica": "text",
            "valor_objetivo": "numeric", "valor_actual": "numeric", "alcanzable": "text",
            "relevante": "text", "fecha_limite": "date",
        },
    },
    {
        "coleccion": "tareas", "tabla": "tareas", "modelo": Tarea, "pk": ["id"],
        "columnas": {
            "id": "uuid", "proyecto_id": "uuid", "titulo": "text", "descripcion": "text",
            "estado": "estado_tarea", "fecha_inicio": "date", "fecha_fin": "date",
            "es_hito": "boolean", "importante": "boolean", "urgente_manual": "boolean",
            "dependencias": "uuid[]", "esfuerzo_estimado_h": "numeric",
            "esfuerzo_real_h": "numeric", "origen_rca": "uuid", "rutina_id": "uuid",
        },
    },
    {
        "coleccion": "retos", "tabla": "retos", "modelo": Reto, "pk": ["id"],
        "columnas": {
            "id": "uuid", "proyecto_id": "uuid", "titulo": "text", "tipo": "tipo_reto",
            "impacto": "int", "probabilidad": "int", "plan_de_respuesta": "text",
            "estado": "estado_reto",
        },
    },
    {
        "coleccion": "documentos", "tabla": "documentos", "modelo": Documento, "pk": ["id"],
        "columnas": {
            "id": "uuid", "proyecto_id": "uuid", "tipo": "tipo_documento", "version": "int",
            "contenido": "jsonb", "historial": "jsonb", "creado_en": "timestamptz",
        },
    },
    {
        "coleccion": "planes_dia", "tabla": "planes_dia", "modelo": PlanDia, "pk": ["fecha"],
        "columnas": {
            "fecha": "date", "tarea_ids": "uuid[]", "cerrado": "boolean", "nota_cierre": "text",
        },
    },
    {
        "coleccion": "snapshots", "tabla": "kpi_snapshots", "modelo": KpiSnapshot,
        "pk": ["proyecto_id", "fecha"],
        "columnas": {
            "proyecto_id": "uuid", "fecha": "date", "avance_pct": "numeric", "spi": "numeric",
            "tareas_vencidas": "int", "retos_abiertos": "int", "salud": "text",
        },
    },
]


# ---------- Funciones puras (con tests, sin red) ----------

def filas_por_tabla(volcado: dict) -> dict[str, dict[tuple, dict]]:
    """Del volcado JSON del almacén a {tabla: {clave_pk: fila}}."""
    resultado: dict[str, dict[tuple, dict]] = {}
    for spec in TABLAS:
        filas = {}
        for item in volcado.get(spec["coleccion"], []):
            fila = {c: item.get(c) for c in spec["columnas"]}
            filas[tuple(fila[k] for k in spec["pk"])] = fila
        resultado[spec["tabla"]] = filas
    return resultado


def calcular_cambios(
    antes: dict[str, dict[tuple, dict]], despues: dict[str, dict[tuple, dict]]
) -> dict[str, dict[str, list]]:
    """Diff por tabla: filas nuevas o modificadas (upsert) y claves que ya no están (delete)."""
    cambios: dict[str, dict[str, list]] = {}
    for tabla, filas in despues.items():
        previas = antes.get(tabla, {})
        upserts = [f for k, f in filas.items() if previas.get(k) != f]
        deletes = [k for k in previas if k not in filas]
        if upserts or deletes:
            cambios[tabla] = {"upserts": upserts, "deletes": deletes}
    return cambios


def a_texto(valor: Any, tipo: str) -> Optional[str]:
    """Valor JSON → literal de texto para castear en Postgres."""
    if valor is None:
        return None
    if tipo == "jsonb":
        return json.dumps(valor, ensure_ascii=False)
    if tipo.endswith("[]"):
        return "{" + ",".join(str(v) for v in valor) + "}"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def de_db(valor: Any) -> Any:
    """Valor leído de Postgres → valor que el modelo Pydantic entiende."""
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, list):
        return [de_db(v) for v in valor]
    if isinstance(valor, datetime) and valor.tzinfo is not None:
        # El almacén usa datetimes "ingenuos" en hora local (como datetime.now()).
        return valor.astimezone(zona()).replace(tzinfo=None)
    return valor


# ---------- Repositorio ----------

class RepositorioSupabase(Repositorio):
    def __init__(self, dsn: str, conectar: Optional[Callable[[], Any]] = None):
        self.dsn = dsn
        self._conectar_fn = conectar
        self._persistido: dict[str, dict[tuple, dict]] = {}
        self._colecciones_vacias()
        self._cargar()

    def _conectar(self):
        if self._conectar_fn is not None:
            return self._conectar_fn()
        import psycopg

        # prepare_threshold=None: compatible también con el pooler de transacciones.
        conexion = psycopg.connect(self.dsn, prepare_threshold=None, connect_timeout=15)
        conexion.execute(f"set time zone '{zona().key or ZONA_DEFECTO}'")
        return conexion

    def _cargar(self) -> None:
        from psycopg.rows import dict_row

        crudo: dict[str, list] = {}
        with self._conectar() as conexion:
            with conexion.cursor(row_factory=dict_row) as cur:
                for spec in TABLAS:
                    columnas = ", ".join(spec["columnas"])
                    cur.execute(f"select {columnas} from {spec['tabla']}")
                    crudo[spec["coleccion"]] = [
                        {k: de_db(v) for k, v in fila.items()} for fila in cur.fetchall()
                    ]
        self._poblar(crudo)
        self._persistido = filas_por_tabla(self.volcado())

    def guardar(self) -> None:
        actual = filas_por_tabla(self.volcado())
        cambios = calcular_cambios(self._persistido, actual)
        if not cambios:
            return
        specs = {s["tabla"]: s for s in TABLAS}
        with self._conectar() as conexion:
            with conexion.transaction():
                # Borrados de hijos a padres; altas de padres a hijos (FKs).
                for spec in reversed(TABLAS):
                    for clave in cambios.get(spec["tabla"], {}).get("deletes", []):
                        condicion = " and ".join(
                            f"{k} = %s::{spec['columnas'][k]}" for k in spec["pk"]
                        )
                        conexion.execute(
                            f"delete from {spec['tabla']} where {condicion}",
                            [a_texto(v, spec["columnas"][k]) for k, v in zip(spec["pk"], clave)],
                        )
                for spec in TABLAS:
                    for fila in cambios.get(spec["tabla"], {}).get("upserts", []):
                        self._upsert(conexion, specs[spec["tabla"]], fila)
        self._persistido = actual

    @staticmethod
    def _upsert(conexion, spec: dict, fila: dict) -> None:
        columnas = list(spec["columnas"])
        valores = ", ".join(f"%s::{spec['columnas'][c]}" for c in columnas)
        no_pk = [c for c in columnas if c not in spec["pk"]]
        actualizar = ", ".join(f"{c} = excluded.{c}" for c in no_pk)
        sql = (
            f"insert into {spec['tabla']} ({', '.join(columnas)}) values ({valores}) "
            f"on conflict ({', '.join(spec['pk'])}) do update set {actualizar}"
        )
        conexion.execute(sql, [a_texto(fila[c], spec["columnas"][c]) for c in columnas])
