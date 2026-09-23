"""Modelos de datos de Comando PM (contratos Pydantic v2).

Son datos puros: el dominio opera sobre ellos sin tocar red ni DB.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from .reloj import ahora_local

EstadoProyecto = Literal["activo", "pausado", "cerrado", "cancelado"]
EstadoTarea = Literal["pendiente", "en_curso", "hecha", "bloqueada"]
TipoReto = Literal["riesgo", "bloqueo", "decision_pendiente"]
EstadoReto = Literal["abierto", "mitigado", "materializado", "cerrado"]
TipoDocumento = Literal["charter", "canvas", "porter", "roadmap", "rca"]
Salud = Literal["verde", "amarillo", "rojo"]

# Captación SINPROTEK (Fase 1)
Etapa = Literal[
    "identificado", "contactado", "reunion_agendada", "demo_hecha",
    "propuesta_enviada", "negociacion", "ganado", "perdido",
]
Origen = Literal["canacintra", "referido", "linkedin", "campo", "llamada_alex", "denue", "otro"]
Segmento = Literal["pyme", "independiente"]
Servicio = Literal["agente_whatsapp", "agente_voz", "consultoria", "capacitacion"]
Canal = Literal["llamada", "whatsapp", "visita", "correo", "reunion", "alex"]


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
    creado_en: datetime = Field(default_factory=ahora_local)


class Objetivo(BaseModel):
    """Objetivo SMART. Validación dura (CLAUDE.md §5.3): los 5 componentes
    son obligatorios y "medible" exige métrica con valor objetivo positivo."""

    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: str
    especifico: str
    metrica: str
    valor_objetivo: float = Field(gt=0)
    valor_actual: float = 0
    alcanzable: str
    relevante: str
    fecha_limite: date

    @field_validator("especifico", "metrica", "alcanzable", "relevante")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("es obligatorio: un objetivo SMART no admite campos vacíos")
        return v.strip()


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
    rutina_id: Optional[str] = None  # instancia diaria generada por una rutina
    prospecto_id: Optional[str] = None  # próxima acción de un prospecto (Ivy Lee la pone primero)

    @model_validator(mode="after")
    def _fechas_coherentes(self):
        """Una tarea invertida distorsiona SPI, semáforo y ruta crítica."""
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("la fecha fin no puede ser anterior a la fecha inicio")
        if self.es_hito and self.fecha_inicio != self.fecha_fin:
            raise ValueError("un hito dura 0 días: fecha inicio y fin deben ser iguales")
        return self


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
    historial: list[dict] = Field(default_factory=list)  # [{version, contenido, fecha}]
    creado_en: datetime = Field(default_factory=ahora_local)


class Rutina(BaseModel):
    """Trabajo recurrente (entreno, prospección, post diario).

    No se pre-crean cientos de tareas: cada día que toca, el dominio genera
    UNA tarea real para ese día (rutina_id) y avanza generada_hasta.
    """

    id: str = Field(default_factory=_nuevo_id)
    proyecto_id: str
    titulo: str
    dias_semana: list[int]  # 0 = lunes … 6 = domingo
    importante: bool = True
    esfuerzo_estimado_h: float = 1
    desde: date
    hasta: Optional[date] = None
    activa: bool = True
    generada_hasta: Optional[date] = None  # último día ya materializado

    @field_validator("titulo")
    @classmethod
    def _titulo(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("la rutina necesita título")
        return v.strip()

    @field_validator("dias_semana")
    @classmethod
    def _dias(cls, v: list[int]) -> list[int]:
        dias = sorted(set(v))
        if not dias or any(d < 0 or d > 6 for d in dias):
            raise ValueError("días de la semana: al menos uno, de 0 (lunes) a 6 (domingo)")
        return dias

    @model_validator(mode="after")
    def _rango(self):
        if self.hasta is not None and self.hasta < self.desde:
            raise ValueError("la rutina no puede terminar antes de empezar")
        return self


class Prospecto(BaseModel):
    """Prospecto de SINPROTEK. La etapa se cambia con dominio.captacion.cambiar_etapa
    (registra fechas_etapa y exige motivo para "perdido")."""

    id: str = Field(default_factory=_nuevo_id)
    empresa: str
    contacto: str = ""
    puesto: str = ""
    telefono: str = ""
    correo: str = ""
    giro: str = ""
    origen: Origen = "otro"
    segmento: Segmento = "pyme"
    servicio: Servicio = "agente_whatsapp"
    etapa: Etapa = "identificado"
    fechas_etapa: dict[str, str] = Field(default_factory=dict)  # {etapa: fecha ISO de entrada}
    fecha_proxima_accion: Optional[date] = None
    proxima_accion: str = ""
    monto_desarrollo: float = Field(default=0, ge=0)
    monto_mensual: float = Field(default=0, ge=0)
    motivo_perdida: str = ""
    link_drive: str = ""
    notas: str = ""
    creado: datetime = Field(default_factory=ahora_local)
    actualizado: datetime = Field(default_factory=ahora_local)

    @field_validator("empresa")
    @classmethod
    def _empresa(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("el prospecto necesita empresa (o nombre)")
        return v.strip()

    @model_validator(mode="after")
    def _motivo(self):
        if self.etapa == "perdido" and not self.motivo_perdida.strip():
            raise ValueError("un prospecto perdido exige motivo de pérdida")
        return self


class Interaccion(BaseModel):
    id: str = Field(default_factory=_nuevo_id)
    prospecto_id: str
    fecha: datetime = Field(default_factory=ahora_local)
    canal: Canal
    resultado: str = ""
    nota: str = ""


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
