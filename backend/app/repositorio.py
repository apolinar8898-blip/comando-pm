"""Repositorio de Comando PM.

v1: almacén en memoria con persistencia a archivo JSON (datos/comando-pm.json).
Suficiente y confiable para una herramienta personal; la migración a Supabase
(schema.sql ya está listo) es un cambio solo de esta capa.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

from .modelos import (
    Documento,
    KpiSnapshot,
    Objetivo,
    PlanDia,
    Proyecto,
    Reto,
    Tarea,
)

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "datos" / "comando-pm.json"


class Repositorio:
    def __init__(self, ruta: Optional[Path] = None):
        self.ruta = ruta if ruta is not None else Path(
            os.environ.get("COMANDO_PM_DATOS", RUTA_DEFECTO)
        )
        self.proyectos: dict[str, Proyecto] = {}
        self.tareas: dict[str, Tarea] = {}
        self.retos: dict[str, Reto] = {}
        self.objetivos: dict[str, Objetivo] = {}
        self.documentos: dict[str, Documento] = {}
        self.planes_dia: dict[str, PlanDia] = {}  # clave: fecha ISO
        self.snapshots: list[KpiSnapshot] = []
        self._cargar()

    # ---------- Persistencia ----------

    def _cargar(self) -> None:
        if not self.ruta.exists():
            return
        crudo = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.proyectos = {d["id"]: Proyecto.model_validate(d) for d in crudo.get("proyectos", [])}
        self.tareas = {d["id"]: Tarea.model_validate(d) for d in crudo.get("tareas", [])}
        self.retos = {d["id"]: Reto.model_validate(d) for d in crudo.get("retos", [])}
        self.objetivos = {d["id"]: Objetivo.model_validate(d) for d in crudo.get("objetivos", [])}
        self.documentos = {d["id"]: Documento.model_validate(d) for d in crudo.get("documentos", [])}
        self.planes_dia = {d["fecha"]: PlanDia.model_validate(d) for d in crudo.get("planes_dia", [])}
        self.snapshots = [KpiSnapshot.model_validate(d) for d in crudo.get("snapshots", [])]

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        crudo = {
            "proyectos": [p.model_dump(mode="json") for p in self.proyectos.values()],
            "tareas": [t.model_dump(mode="json") for t in self.tareas.values()],
            "retos": [r.model_dump(mode="json") for r in self.retos.values()],
            "objetivos": [o.model_dump(mode="json") for o in self.objetivos.values()],
            "documentos": [d.model_dump(mode="json") for d in self.documentos.values()],
            "planes_dia": [p.model_dump(mode="json") for p in self.planes_dia.values()],
            "snapshots": [s.model_dump(mode="json") for s in self.snapshots],
        }
        self.ruta.write_text(json.dumps(crudo, ensure_ascii=False, indent=1), encoding="utf-8")

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
