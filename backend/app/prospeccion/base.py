"""Conexión propia a Supabase para las tablas pq_* (no pasan por el repositorio en memoria)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "backend" / "datos" / "prospeccion"   # descargas; backend/datos/ está en .gitignore


def preparar_consola() -> None:
    """La consola de Windows no siempre es UTF-8: que los acentos no truenen."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def cargar_env() -> None:
    """Lee RAIZ/.env (CLAVE=valor por línea) sin pisar variables ya definidas."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def conectar():
    """Conexión psycopg a la misma DB de Comando PM (DATABASE_URL, Session pooler)."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Falta DATABASE_URL en el .env de la raíz: la base de prospección vive en Supabase.")
    import psycopg

    from ..repositorio_supabase import limpiar_dsn

    return psycopg.connect(limpiar_dsn(dsn), prepare_threshold=None, connect_timeout=15)
