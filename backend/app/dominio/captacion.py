"""Captación SINPROTEK: reglas del CRM de prospectos (Fase 1, CLAUDE.md §12).

Meta que gobierna todo: 3 clientes pagando antes del 31/12/2026.
Funciones puras: reciben prospectos/interacciones y devuelven valores.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from ..modelos import Interaccion, Prospecto, Salud, Tarea

META_CLIENTES = 3
FECHA_META = date(2026, 12, 31)
DIAS_SIN_CONTACTO = 7          # más de 7 días sin interacción → 🔴
MAX_SIN_CONTACTO_SANO = 3      # más de 3 prospectos así → proyecto 🔴
RITMO_MINIMO = 0.5             # ritmo semanal < 50 % de la meta → proyecto 🔴
META_SEMANA_DEFECTO = 25       # 5 por día hábil

# Embudo en orden. "perdido" queda fuera: es una salida desde cualquier etapa.
EMBUDO = [
    "identificado", "contactado", "reunion_agendada", "demo_hecha",
    "propuesta_enviada", "negociacion", "ganado",
]
CERRADAS = {"ganado", "perdido"}

PROBABILIDAD_DEFECTO = {
    "identificado": 0.05, "contactado": 0.10, "reunion_agendada": 0.20,
    "demo_hecha": 0.35, "propuesta_enviada": 0.50, "negociacion": 0.70,
}

# Precios fijos (MXN): (desarrollo, mensualidad)
PRECIOS = {"pyme": (4000.0, 4000.0), "independiente": (3000.0, 3500.0)}


# ---------- Montos y etapas ----------

def montos_por_segmento(segmento: str) -> tuple[float, float]:
    """Montos precargados según segmento (editables después)."""
    return PRECIOS[segmento]


def activo(p: Prospecto) -> bool:
    return p.etapa not in CERRADAS


def cambiar_etapa(p: Prospecto, nueva: str, hoy: date, motivo: str = "") -> Prospecto:
    """Mueve el prospecto y registra la fecha de entrada a la etapa (solo la
    primera vez: la conversión cuenta a quién llegó, no cuántas veces).
    "perdido" exige motivo: sin él no se sabe qué corregir."""
    datos = p.model_dump()
    datos["etapa"] = nueva
    if nueva == "perdido":
        datos["motivo_perdida"] = (motivo or p.motivo_perdida).strip()
    fechas = dict(p.fechas_etapa)
    fechas.setdefault(nueva, hoy.isoformat())
    datos["fechas_etapa"] = fechas
    return Prospecto.model_validate(datos)  # valida el motivo obligatorio


def etapa_maxima(p: Prospecto) -> int:
    """Índice en EMBUDO de la etapa más avanzada a la que llegó (aunque luego
    se haya perdido). Llegar a una etapa implica haber pasado las anteriores."""
    alcanzadas = [EMBUDO.index(e) for e in [*p.fechas_etapa, p.etapa] if e in EMBUDO]
    return max(alcanzadas, default=0)


# ---------- Contacto y alertas ----------

def normalizar_telefono(telefono: str) -> str:
    """Últimos 10 dígitos: +52 1 442 123 4567 y 442-123-4567 son el mismo."""
    return re.sub(r"\D", "", telefono or "")[-10:]


def ultimo_contacto(p: Prospecto, interacciones: list[Interaccion]) -> date:
    """Fecha de la última interacción; sin ninguna, la fecha de alta."""
    propias = [i.fecha for i in interacciones if i.prospecto_id == p.id]
    return max(propias, default=p.creado).date()


def alertas(p: Prospecto, interacciones: list[Interaccion], hoy: date) -> list[str]:
    """🔴 del prospecto: próxima acción vencida o > 7 días sin interacción."""
    if not activo(p):
        return []
    motivos = []
    if p.fecha_proxima_accion is not None and p.fecha_proxima_accion < hoy:
        motivos.append("accion_vencida")
    if (hoy - ultimo_contacto(p, interacciones)).days > DIAS_SIN_CONTACTO:
        motivos.append("sin_contacto")
    return motivos


# ---------- Ritmo semanal ----------

def inicio_semana(hoy: date) -> date:
    return hoy - timedelta(days=hoy.weekday())


def interacciones_semana(interacciones: list[Interaccion], hoy: date) -> int:
    lunes = inicio_semana(hoy)
    return sum(1 for i in interacciones if lunes <= i.fecha.date() <= hoy)


def ritmo_semanal(hechas: int, meta: int, hoy: date) -> Optional[float]:
    """Hechas vs lo que YA debería llevarse (como el SPI): se cuentan solo los
    días hábiles completados antes de hoy. Lunes → None (aún no hay con qué
    comparar); así el lunes a las 8:00 no amanece en rojo."""
    dias_habiles = min(hoy.weekday(), 5)
    esperado = meta * dias_habiles / 5
    if esperado <= 0:
        return None
    return hechas / esperado


# ---------- KPIs y salud ----------

def conversion(prospectos: list[Prospecto]) -> list[dict]:
    """De los que llegaron a cada etapa, cuántos llegaron a la siguiente."""
    maximos = [etapa_maxima(p) for p in prospectos]
    filas = []
    for k in range(len(EMBUDO) - 1):
        llegaron = sum(1 for m in maximos if m >= k)
        pasaron = sum(1 for m in maximos if m >= k + 1)
        filas.append({
            "de": EMBUDO[k], "a": EMBUDO[k + 1], "llegaron": llegaron, "pasaron": pasaron,
            "pct": round(100 * pasaron / llegaron, 1) if llegaron else None,
        })
    return filas


def kpis_captacion(
    prospectos: list[Prospecto],
    interacciones: list[Interaccion],
    hoy: date,
    meta_semana: int = META_SEMANA_DEFECTO,
    probabilidades: Optional[dict[str, float]] = None,
) -> dict:
    prob = {**PROBABILIDAD_DEFECTO, **(probabilidades or {})}
    ganados = [p for p in prospectos if p.etapa == "ganado"]
    activos = [p for p in prospectos if activo(p)]
    en_semana = interacciones_semana(interacciones, hoy)
    ritmo = ritmo_semanal(en_semana, meta_semana, hoy)
    con_alerta = {p.id: alertas(p, interacciones, hoy) for p in activos}
    return {
        "ganados": len(ganados),
        "meta_clientes": META_CLIENTES,
        "dias_restantes": (FECHA_META - hoy).days,
        "mrr_actual": sum(p.monto_mensual for p in ganados),
        "mrr_ponderado": round(sum(p.monto_mensual * prob.get(p.etapa, 0) for p in activos), 2),
        "por_etapa": {e: sum(1 for p in prospectos if p.etapa == e) for e in [*EMBUDO, "perdido"]},
        "conversion": conversion(prospectos),
        "interacciones_semana": en_semana,
        "meta_semana": meta_semana,
        "ritmo": None if ritmo is None else round(ritmo, 2),
        "con_alerta": sum(1 for m in con_alerta.values() if m),
        "sin_contacto": sum(1 for m in con_alerta.values() if "sin_contacto" in m),
        "acciones_vencidas": sum(1 for m in con_alerta.values() if "accion_vencida" in m),
    }


def salud_captacion(kpis: dict) -> Salud:
    """🔴 si > 3 prospectos sin contacto > 7 días o ritmo < 50 % de la meta."""
    ritmo = kpis["ritmo"]
    if kpis["sin_contacto"] > MAX_SIN_CONTACTO_SANO or (ritmo is not None and ritmo < RITMO_MINIMO):
        return "rojo"
    return "verde"


ORDEN_SALUD = {"verde": 0, "amarillo": 1, "rojo": 2}


def peor(a: Salud, b: Salud) -> Salud:
    return a if ORDEN_SALUD[a] >= ORDEN_SALUD[b] else b


# ---------- Próxima acción → tarea real (Ivy Lee) ----------

def titulo_accion(p: Prospecto) -> str:
    return f"{p.proxima_accion.strip() or 'Seguimiento'} — {p.empresa}"


def tarea_de_accion(p: Prospecto, pendiente: Optional[Tarea], proyecto_id: str) -> Optional[Tarea]:
    """La tarea que debe existir para la próxima acción del prospecto.

    Devuelve la tarea (nueva o actualizada) o None si no debe haber ninguna
    (prospecto cerrado o sin fecha de próxima acción)."""
    if not activo(p) or p.fecha_proxima_accion is None:
        return None
    datos = {
        "proyecto_id": proyecto_id,
        "titulo": titulo_accion(p),
        "fecha_inicio": p.fecha_proxima_accion,
        "fecha_fin": p.fecha_proxima_accion,
        "importante": True,
        "esfuerzo_estimado_h": 0.25,
        "prospecto_id": p.id,
    }
    if pendiente is not None:
        return pendiente.model_copy(update=datos)
    return Tarea(**datos)
