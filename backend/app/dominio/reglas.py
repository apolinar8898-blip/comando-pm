"""Reglas de negocio: salud, avance, SPI y matriz de Eisenhower.

Todas son funciones puras: reciben datos, devuelven valores.
La salud del proyecto SE CALCULA, nunca se opina (CLAUDE.md §3).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from ..modelos import Reto, Salud, Tarea
from .rutinas import rutina_expirada

# Umbrales de la regla de salud (una sola fuente de verdad)
SPI_ROJO = 0.8
SPI_AMARILLO = 0.95
RIESGO_ROJO = 16  # impacto × probabilidad
RIESGO_AMARILLO = 9
DIAS_URGENCIA = 2  # una tarea es urgente si vence en ≤ 2 días


# ---------- Eisenhower ----------

def es_urgente(tarea: Tarea, hoy: date) -> bool:
    """Urgencia manual si el usuario la fijó; si no, automática por fecha."""
    if tarea.urgente_manual is not None:
        return tarea.urgente_manual
    return tarea.fecha_fin <= hoy + timedelta(days=DIAS_URGENCIA)


def cuadrante_eisenhower(tarea: Tarea, hoy: date) -> int:
    """1: urgente+importante · 2: importante · 3: urgente · 4: ninguno."""
    urgente = es_urgente(tarea, hoy)
    if urgente and tarea.importante:
        return 1
    if tarea.importante:
        return 2
    if urgente:
        return 3
    return 4


# ---------- Avance y SPI ----------

def avance(tareas: list[Tarea]) -> float:
    """Avance ponderado por esfuerzo estimado (0.0 a 1.0). Sin tareas = 0."""
    total = sum(t.esfuerzo_estimado_h for t in tareas)
    if total <= 0:
        return 0.0
    hecho = sum(t.esfuerzo_estimado_h for t in tareas if t.estado == "hecha")
    return hecho / total


def _fraccion_planificada(tarea: Tarea, hoy: date) -> float:
    """Qué fracción de la tarea debería estar hecha a hoy, lineal por fechas.

    Cuenta solo días COMPLETADOS antes de hoy: el día que arranca una tarea
    su valor planificado es 0 (nadie está atrasado el día 1).
    """
    if hoy > tarea.fecha_fin:
        return 1.0
    if hoy <= tarea.fecha_inicio:
        return 0.0
    dias_totales = (tarea.fecha_fin - tarea.fecha_inicio).days + 1
    dias_completados = (hoy - tarea.fecha_inicio).days
    return dias_completados / dias_totales


def _valor_ganado(tarea: Tarea) -> float:
    """Hecha = 100% del esfuerzo; en curso = 50%; lo demás = 0."""
    if tarea.estado == "hecha":
        return tarea.esfuerzo_estimado_h
    if tarea.estado == "en_curso":
        return tarea.esfuerzo_estimado_h * 0.5
    return 0.0


def spi(tareas: list[Tarea], hoy: date) -> float:
    """SPI simplificado (EVM del PMBOK): valor ganado / valor planificado.

    Sin valor planificado aún (proyecto no arrancado) → 1.0 (en plan).
    """
    valor_planificado = sum(
        t.esfuerzo_estimado_h * _fraccion_planificada(t, hoy) for t in tareas
    )
    if valor_planificado <= 0:
        return 1.0
    return sum(_valor_ganado(t) for t in tareas) / valor_planificado


# ---------- Vencimientos e hitos ----------

def tareas_vencidas(tareas: list[Tarea], hoy: date) -> list[Tarea]:
    """Pendientes con fecha pasada. Las instancias de rutina expiradas no
    cuentan (un entreno de ayer no se recupera): su falta ya pesa en el SPI."""
    return [
        t for t in tareas
        if t.estado != "hecha" and t.fecha_fin < hoy and not rutina_expirada(t, hoy)
    ]


def hitos_vencidos(tareas: list[Tarea], hoy: date) -> list[Tarea]:
    return [t for t in tareas_vencidas(tareas, hoy) if t.es_hito]


def proximo_hito(tareas: list[Tarea], hoy: date) -> Optional[Tarea]:
    """El hito pendiente más cercano (vencido o futuro: lo que sigue en el radar)."""
    pendientes = [t for t in tareas if t.es_hito and t.estado != "hecha"]
    if not pendientes:
        return None
    return min(pendientes, key=lambda t: t.fecha_fin)


# ---------- Salud (el semáforo) ----------

def _mayor_riesgo_abierto(retos: list[Reto]) -> int:
    abiertos = [r for r in retos if r.estado == "abierto"]
    if not abiertos:
        return 0
    return max(r.impacto * r.probabilidad for r in abiertos)


def salud_proyecto(tareas: list[Tarea], retos: list[Reto], hoy: date) -> Salud:
    """Regla del CLAUDE.md §3 — calculada, jamás manual.

    ROJO:     hito vencido, o SPI < 0.8, o reto abierto con impacto×prob ≥ 16.
    AMARILLO: tareas vencidas, o SPI < 0.95, o reto abierto ≥ 9.
    VERDE:    todo lo demás.
    """
    riesgo = _mayor_riesgo_abierto(retos)
    indice = spi(tareas, hoy)

    if hitos_vencidos(tareas, hoy) or indice < SPI_ROJO or riesgo >= RIESGO_ROJO:
        return "rojo"
    if tareas_vencidas(tareas, hoy) or indice < SPI_AMARILLO or riesgo >= RIESGO_AMARILLO:
        return "amarillo"
    return "verde"
