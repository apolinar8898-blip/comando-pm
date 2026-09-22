"""Utilidades de los scripts: cargar el .env de la raíz y hacer importable app/."""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
# La consola de Windows no siempre es UTF-8: que los acentos y ✅ no truenen.
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
