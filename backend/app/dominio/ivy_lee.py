"""Método Ivy Lee: máximo 6 tareas al día, ordenadas por prioridad.

El límite es DURO (CLAUDE.md §3): la app no permite la séptima.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..modelos import Tarea
from .reglas import cuadrante_eisenhower
from .rutinas import rutina_expirada

MAX_TAREAS_DIA = 6
DIAS_RADAR_HITOS = 7  # hitos que vencen en ≤ 7 días entran primero al plan


def sugerir_plan_dia(tareas: list[Tarea], hoy: date) -> list[str]:
    """Propone las 6 tareas del día a partir de las pendientes.

    Prioridad: hitos próximos (≤7 días) → cuadrante I → cuadrante II,
    cada grupo ordenado por fecha de vencimiento. Excluye bloqueadas, hechas
    y rutinas expiradas (el entreno de ayer no se hace hoy).
    Devuelve ids en orden (el usuario luego reordena/reemplaza y confirma).
    """
    candidatas = [
        t for t in tareas
        if t.estado in ("pendiente", "en_curso") and not rutina_expirada(t, hoy)
    ]

    hitos = sorted(
        (t for t in candidatas
         if t.es_hito and t.fecha_fin <= hoy + timedelta(days=DIAS_RADAR_HITOS)),
        key=lambda t: t.fecha_fin,
    )
    resto = [t for t in candidatas if t not in hitos]
    cuadrante_1 = sorted(
        (t for t in resto if cuadrante_eisenhower(t, hoy) == 1),
        key=lambda t: t.fecha_fin,
    )
    cuadrante_2 = sorted(
        (t for t in resto if cuadrante_eisenhower(t, hoy) == 2),
        key=lambda t: t.fecha_fin,
    )

    plan: list[str] = []
    for tarea in hitos + cuadrante_1 + cuadrante_2:
        if len(plan) >= MAX_TAREAS_DIA:
            break
        plan.append(tarea.id)
    return plan


def acciones_prospeccion(tareas: list[Tarea], hoy: date) -> list[str]:
    """Próximas acciones de prospectos vencidas o de hoy, las más viejas primero.

    Regla de Apo (Fase 1): van ANTES que cualquier otra tarea del plan.
    """
    propias = [
        t for t in tareas
        if t.prospecto_id and t.estado in ("pendiente", "en_curso") and t.fecha_fin <= hoy
    ]
    return [t.id for t in sorted(propias, key=lambda t: t.fecha_fin)]


def componer_plan(
    prospeccion: list[str], arrastradas: list[str], sugeridas: list[str],
    tope_prospeccion: int = MAX_TAREAS_DIA,
) -> list[str]:
    """Plan del día: prospección (hasta el tope) → pendientes de ayer → sugerencia.

    Sin duplicados y máximo 6. Con tope 6 la prospección puede llenar el día:
    es la regla elegida por Apo (meta de 3 clientes), configurable.
    """
    plan: list[str] = []
    for grupo in (prospeccion[:tope_prospeccion], arrastradas, sugeridas):
        for tid in grupo:
            if tid not in plan and len(plan) < MAX_TAREAS_DIA:
                plan.append(tid)
    return plan


def validar_plan(tarea_ids: list[str]) -> list[str]:
    """Aplica el límite duro: sin duplicados y máximo 6."""
    unicos: list[str] = []
    for tid in tarea_ids:
        if tid not in unicos:
            unicos.append(tid)
    if len(unicos) > MAX_TAREAS_DIA:
        raise ValueError(
            f"El plan del día admite máximo {MAX_TAREAS_DIA} tareas (método Ivy Lee). "
            "Si necesitas más, el problema es de priorización, no de espacio."
        )
    return unicos
