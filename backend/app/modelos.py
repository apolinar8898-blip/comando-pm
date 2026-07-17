"""Modelos de datos de Comando PM (contratos Pydantic v2).

Son datos puros: el dominio opera sobre ellos sin tocar red ni DB.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

EstadoProyecto = Literal["activo", "pausado", "cerrado", "cancelado"]
EstadoTarea = Literal["pendiente", "en_curso", "hecha", "bloqueada"]
TipoReto = Literal["riesgo", "bloqueo", "decision_pendiente"]
EstadoReto = Literal["abierto", "mitigado", "materializado", "cerrado"]
TipoDocumento = Literal["charter", "canvas", "porter", "roadmap", "rca"]
Salud = Literal["verde", "amarillo", "rojo"]


def _nuevo_id() -> str:
    return str(uuid4())


class Proyecto(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    nombre: str
    descripcion: str = ""
    estado: EstadoProyecto = "activo"
    fecha_inicio: date
    fecha_fin_objetivo: date
    color: str = "#4f46e5"
    prioridad: int = 3  # 1 (alta) a 5 (baja)
    fase: str = ""
    fase_inicio: Optional[date] = None
    fase_fin: Optional[date] = None
    lecciones: str = ""
    creado_en: datetime = Field(default_factory=datetime.now)


class Objetivo(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: str
    especifico: str
    metrica: str
    valor_objetivo: float
    valor_actual: float = 0
    alcanzable: str
    relevante: str
    fecha_limite: date


class Tarea(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: str
    titulo: str
    descripcion: str = ""
    estado: EstadoTarea = "pendiente"
    fecha_inicio: date
    fecha_fin: date
    es_hito: bool = False
    importante: bool = False
    urgente_manual: Optional[bool] = None  # None = urgencia automática por fecha
    dependencias: list[str] = Field(default_factory=list)
    esfuerzo_estimado_h: float = 1
    esfuerzo_real_h: Optional[float] = None
    origen_rca: Optional[str] = None


class Reto(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: str
    titulo: str
    tipo: TipoReto = "riesgo"
    impacto: int = Field(ge=1, le=5)
    probabilidad: int = Field(ge=1, le=5)
    plan_de_respuesta: str = ""
    estado: EstadoReto = "abierto"


class Documento(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: Optional[str] = None  # None = nivel portafolio
    tipo: TipoDocumento
    version: int = 1
    contenido: dict = Field(default_factory=dict)
    creado_en: datetime = Field(default_factory=datetime.now)


class PlanDia(BaseModel):
    fecha: date
    tarea_ids: list[str] = Field(default_factory=list)  # orden = prioridad; máx. 6
    cerrado: bool = False
    nota_cierre: str = ""


class KpiSnapshot(BaseModel):
    proyecto_id: str
    fecha: date
    avance_pct: float
    spi: float
    tareas_vencidas: int
    retos_abiertos: int
    salud: Salud
