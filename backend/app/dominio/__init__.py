"""Dominio de Comando PM: lógica de negocio pura, sin red ni DB.

Cada regla del CLAUDE.md §3 vive aquí y tiene su test en pruebas/.
"""
from .reglas import (
    avance,
    cuadrante_eisenhower,
    es_urgente,
    hitos_vencidos,
    proximo_hito,
    salud_proyecto,
    spi,
    tareas_vencidas,
)
from .ivy_lee import MAX_TAREAS_DIA, acciones_prospeccion, componer_plan, sugerir_plan_dia, validar_plan
from .gantt import ruta_critica
from .rutinas import fechas_a_generar, instancia, rutina_expirada

__all__ = [
    "avance",
    "cuadrante_eisenhower",
    "es_urgente",
    "hitos_vencidos",
    "proximo_hito",
    "salud_proyecto",
    "spi",
    "tareas_vencidas",
    "MAX_TAREAS_DIA",
    "acciones_prospeccion",
    "componer_plan",
    "sugerir_plan_dia",
    "validar_plan",
    "ruta_critica",
    "fechas_a_generar",
    "instancia",
    "rutina_expirada",
]
