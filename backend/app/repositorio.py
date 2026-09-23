"""Repositorio de Comando PM.

Almacén en memoria (dicts de modelos Pydantic) con dos persistencias:
- Repositorio (este archivo, JSON en datos/comando-pm.json): tests, desarrollo
  local y respaldo.
- RepositorioSupabase (repositorio_supabase.py): producción. Se elige con
  crear_repositorio() según exista DATABASE_URL.

Blindaje de la persistencia (dictamen del consejo):
- Escritura atómica: tmp + os.replace, nunca truncar el archivo en el lugar.
- Respaldo diario en datos/respaldos/ (retiene los últimos 30).
- Archivo corrupto: se aparta con marca de tiempo, se recupera del último
  respaldo, y si no hay, se arranca vacío — la app nunca se vuelve inarrancable.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .modelos import (
    Documento,
    Interaccion,
    KpiSnapshot,
    Objetivo,
    PlanDia,
    Proyecto,
    Prospecto,
    Reto,
    Rutina,
    Tarea,
)

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "datos" / "comando-pm.json"


class Repositorio:
    def __init__(self, ruta: Optional[Path] = None):
        self.ruta = ruta if ruta is not None else Path(
            os.environ.get("COMANDO_PM_DATOS", RUTA_DEFECTO)
        )
        self._colecciones_vacias()
        self._cargar()

    def _colecciones_vacias(self) -> None:
        self.proyectos: dict[str, Proyecto] = {}
        self.tareas: dict[str, Tarea] = {}
        self.retos: dict[str, Reto] = {}
        self.objetivos: dict[str, Objetivo] = {}
        self.documentos: dict[str, Documento] = {}
        self.planes_dia: dict[str, PlanDia] = {}  # clave: fecha ISO
        self.snapshots: list[KpiSnapshot] = []
        self.rutinas: dict[str, Rutina] = {}
        self.prospectos: dict[str, Prospecto] = {}
        self.interacciones: dict[str, Interaccion] = {}
        self.configuracion: dict[str, object] = {}  # clave → valor JSON

    # ---------- Persistencia ----------

    @property
    def _dir_respaldos(self) -> Path:
        return self.ruta.parent / "respaldos"

    def _poblar(self, crudo: dict) -> None:
        self.proyectos = {d["id"]: Proyecto.model_validate(d) for d in crudo.get("proyectos", [])}
        self.tareas = {d["id"]: Tarea.model_validate(d) for d in crudo.get("tareas", [])}
        self.retos = {d["id"]: Reto.model_validate(d) for d in crudo.get("retos", [])}
        self.objetivos = {d["id"]: Objetivo.model_validate(d) for d in crudo.get("objetivos", [])}
        self.documentos = {d["id"]: Documento.model_validate(d) for d in crudo.get("documentos", [])}
        # Clave ISO siempre, venga de JSON (texto) o de Postgres (date).
        planes = (PlanDia.model_validate(d) for d in crudo.get("planes_dia", []))
        self.planes_dia = {p.fecha.isoformat(): p for p in planes}
        self.snapshots = [KpiSnapshot.model_validate(d) for d in crudo.get("snapshots", [])]
        self.rutinas = {d["id"]: Rutina.model_validate(d) for d in crudo.get("rutinas", [])}
        self.prospectos = {d["id"]: Prospecto.model_validate(d) for d in crudo.get("prospectos", [])}
        self.interacciones = {
            d["id"]: Interaccion.model_validate(d) for d in crudo.get("interacciones", [])
        }
        self.configuracion = {d["clave"]: d["valor"] for d in crudo.get("configuracion", [])}

    def _cargar(self) -> None:
        if not self.ruta.exists():
            return
        try:
            self._poblar(json.loads(self.ruta.read_text(encoding="utf-8")))
            return
        except Exception as e:  # JSON roto o datos inválidos: nunca morir al arrancar
            marca = datetime.now().strftime("%Y%m%d-%H%M%S")
            danado = self.ruta.with_name(f"{self.ruta.stem}.corrupto-{marca}.json")
            self.ruta.replace(danado)
            print(f"[comando-pm] ADVERTENCIA: archivo de datos dañado ({e}). "
                  f"Se apartó en {danado.name}; intentando recuperar del último respaldo…")

        respaldos = sorted(self._dir_respaldos.glob(f"{self.ruta.stem}-*.json"), reverse=True)
        for respaldo in respaldos:
            try:
                self._poblar(json.loads(respaldo.read_text(encoding="utf-8")))
                shutil.copy2(respaldo, self.ruta)
                print(f"[comando-pm] Recuperado del respaldo {respaldo.name}.")
                return
            except Exception:
                continue
        print("[comando-pm] Sin respaldo utilizable: se arranca con datos vacíos. "
              "El archivo dañado sigue disponible junto a los datos.")

    def volcado(self) -> dict:
        """Serialización completa del almacén (persistencia y export comparten esto)."""
        return {
            "proyectos": [p.model_dump(mode="json") for p in self.proyectos.values()],
            "tareas": [t.model_dump(mode="json") for t in self.tareas.values()],
            "retos": [r.model_dump(mode="json") for r in self.retos.values()],
            "objetivos": [o.model_dump(mode="json") for o in self.objetivos.values()],
            "documentos": [d.model_dump(mode="json") for d in self.documentos.values()],
            "planes_dia": [p.model_dump(mode="json") for p in self.planes_dia.values()],
            "snapshots": [s.model_dump(mode="json") for s in self.snapshots],
            "rutinas": [r.model_dump(mode="json") for r in self.rutinas.values()],
            "prospectos": [p.model_dump(mode="json") for p in self.prospectos.values()],
            "interacciones": [i.model_dump(mode="json") for i in self.interacciones.values()],
            "configuracion": [{"clave": k, "valor": v} for k, v in self.configuracion.items()],
        }

    def _respaldo_diario(self) -> None:
        """Primera escritura del día: copia el archivo actual a respaldos/ (retiene 30)."""
        if not self.ruta.exists():
            return
        destino = self._dir_respaldos / f"{self.ruta.stem}-{date.today().isoformat()}.json"
        if destino.exists():
            return
        self._dir_respaldos.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.ruta, destino)
        viejos = sorted(self._dir_respaldos.glob(f"{self.ruta.stem}-*.json"))[:-30]
        for viejo in viejos:
            viejo.unlink()

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._respaldo_diario()
        contenido = json.dumps(self.volcado(), ensure_ascii=False, indent=1)
        tmp = self.ruta.with_name(self.ruta.name + ".tmp")
        tmp.write_text(contenido, encoding="utf-8")
        os.replace(tmp, self.ruta)  # rename atómico: nunca queda un archivo a medias

    # ---------- Consultas ----------

    def tareas_de(self, proyecto_id: str) -> list[Tarea]:
        return [t for t in self.tareas.values() if t.proyecto_id == proyecto_id]

    def retos_de(self, proyecto_id: str) -> list[Reto]:
        return [r for r in self.retos.values() if r.proyecto_id == proyecto_id]

    def objetivos_de(self, proyecto_id: str) -> list[Objetivo]:
        return [o for o in self.objetivos.values() if o.proyecto_id == proyecto_id]

    def proyectos_activos(self) -> list[Proyecto]:
        activos = [p for p in self.proyectos.values() if p.estado == "activo"]
        return sorted(activos, key=lambda p: (p.prioridad, p.fecha_fin_objetivo))

    def tareas_de_activos(self) -> list[Tarea]:
        ids_activos = {p.id for p in self.proyectos_activos()}
        return [t for t in self.tareas.values() if t.proyecto_id in ids_activos]

    def snapshots_de(self, proyecto_id: str) -> list[KpiSnapshot]:
        propios = [s for s in self.snapshots if s.proyecto_id == proyecto_id]
        return sorted(propios, key=lambda s: s.fecha)

    def snapshot_existe(self, proyecto_id: str, fecha: date) -> bool:
        return any(s.proyecto_id == proyecto_id and s.fecha == fecha for s in self.snapshots)

    def plan_de(self, fecha: date) -> Optional[PlanDia]:
        return self.planes_dia.get(fecha.isoformat())

    def poner_plan(self, plan: PlanDia) -> None:
        self.planes_dia[plan.fecha.isoformat()] = plan

    def vacio(self) -> bool:
        return not self.proyectos

    def interacciones_de(self, prospecto_id: str) -> list[Interaccion]:
        propias = [i for i in self.interacciones.values() if i.prospecto_id == prospecto_id]
        return sorted(propias, key=lambda i: i.fecha, reverse=True)

    def accion_pendiente(self, prospecto_id: str) -> Optional[Tarea]:
        """La tarea abierta de la próxima acción de un prospecto (a lo más una)."""
        return next(
            (t for t in self.tareas.values()
             if t.prospecto_id == prospecto_id and t.estado in ("pendiente", "en_curso")),
            None,
        )

    def proyecto_captacion(self) -> Optional[Proyecto]:
        """El proyecto de SINPROTEK: por configuración o, si no, por nombre."""
        pid = self.configuracion.get("proyecto_captacion_id")
        if pid in self.proyectos:
            return self.proyectos[pid]
        return next(
            (p for p in self.proyectos.values()
             if p.nombre.lower().startswith("sinprotek") and p.estado == "activo"),
            None,
        )

    def proyecto_por_nombre(self, nombre: str) -> Optional[Proyecto]:
        clave = nombre.strip().lower()
        return next((p for p in self.proyectos.values() if p.nombre.strip().lower() == clave), None)


def crear_repositorio() -> Repositorio:
    """Supabase si hay DATABASE_URL (producción); si no, archivo JSON."""
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        from .repositorio_supabase import RepositorioSupabase
        return _con_espera(lambda: RepositorioSupabase(dsn))
    return Repositorio()


def _con_espera(crear, dormir=None) -> Repositorio:
    """Si la DB rechaza la conexión al arrancar, esperar antes de caer.

    Sin esto Railway reinicia en ráfaga y, con una contraseña mala, Supabase
    bloquea la cuenta (ECIRCUITBREAKER: too many authentication failures).
    """
    import time

    try:
        return crear()
    except Exception as e:
        espera = int(os.environ.get("ESPERA_REINTENTO_DB", "60"))
        print(f"[comando-pm] No se pudo conectar a la base de datos: {type(e).__name__}. "
              f"Revisa DATABASE_URL. Reintento tras {espera} s.")
        (dormir or time.sleep)(espera)
        raise
