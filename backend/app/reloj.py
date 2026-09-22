"""El "hoy" de la app es el de Querétaro, no el del servidor.

Railway corre en UTC: con date.today() la app creería que ya es mañana
desde las 18:00 de Querétaro (Ivy Lee, vencidas y SPI mal). Zona
configurable con ZONA_HORARIA (por defecto America/Mexico_City, UTC−6).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ZONA_DEFECTO = "America/Mexico_City"


def zona() -> ZoneInfo:
    return ZoneInfo(os.environ.get("ZONA_HORARIA", ZONA_DEFECTO))


def hoy_en(instante_utc: datetime, zona_: ZoneInfo) -> date:
    """Fecha local de un instante UTC (función pura, con test)."""
    return instante_utc.astimezone(zona_).date()


def hoy_local(ahora_utc: Optional[datetime] = None) -> date:
    return hoy_en(ahora_utc or datetime.now(timezone.utc), zona())
