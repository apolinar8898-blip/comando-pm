"""Rutinas: trabajo recurrente que se materializa en tareas día por día.

Reglas (CLAUDE.md §11, Fase 0):
- Una rutina genera UNA tarea real por cada día que le toca, solo hasta hoy
  (nunca a futuro: si no, Ivy Lee se llenaría con los entrenos de mañana).
- Los días sin abrir la app también se generan (máx. MAX_DIAS_RELLENO hacia
  atrás): un entreno que no se marcó cuenta como no hecho. Es honesto.
- Una instancia de rutina de un día pasado "expira": no cuenta como vencida
  (un entreno de ayer no se recupera hoy) ni se sugiere en Ivy Lee, pero SÍ
  pesa en el SPI, que así mide la adherencia al plan.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..modelos import Rutina, Tarea

MAX_DIAS_RELLENO = 31
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fechas_a_generar(rutina: Rutina, hoy: date) -> list[date]:
    """Días (≤ hoy) en que la rutina toca y aún no se materializaron."""
    if not rutina.activa:
        return []
    inicio = rutina.desde
    if rutina.generada_hasta is not None:
        inicio = max(inicio, rutina.generada_hasta + timedelta(days=1))
    inicio = max(inicio, hoy - timedelta(days=MAX_DIAS_RELLENO - 1))
    fin = hoy if rutina.hasta is None else min(hoy, rutina.hasta)

    fechas = []
    dia = inicio
    while dia <= fin:
        if dia.weekday() in rutina.dias_semana:
            fechas.append(dia)
        dia += timedelta(days=1)
    return fechas


def instancia(rutina: Rutina, fecha: date) -> Tarea:
    """La tarea real de un día de la rutina."""
    return Tarea(
        proyecto_id=rutina.proyecto_id,
        titulo=rutina.titulo,
        fecha_inicio=fecha,
        fecha_fin=fecha,
        importante=rutina.importante,
        esfuerzo_estimado_h=rutina.esfuerzo_estimado_h,
        rutina_id=rutina.id,
    )


def rutina_expirada(tarea: Tarea, hoy: date) -> bool:
    """Instancia de rutina de un día pasado que no se hizo: ya no se recupera."""
    return tarea.rutina_id is not None and tarea.estado != "hecha" and tarea.fecha_fin < hoy
