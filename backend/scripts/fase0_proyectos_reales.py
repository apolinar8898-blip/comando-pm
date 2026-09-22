r"""Fase 0: archiva las demos, cancela Zenzontle y crea los proyectos reales.

Uso (desde la carpeta backend):
    .venv\Scripts\python scripts\fase0_proyectos_reales.py          # sobre Supabase (DATABASE_URL del .env)
    .venv\Scripts\python scripts\fase0_proyectos_reales.py --json   # sobre el archivo JSON local

Idempotente: correrlo de nuevo no duplica nada.
"""
from __future__ import annotations

import os
import sys

from _entorno import cargar_env

from app.reloj import hoy_local
from app.repositorio import Repositorio, crear_repositorio
from app.semilla_real import aplicar_fase0


def main() -> int:
    cargar_env()
    if "--json" in sys.argv:
        os.environ.pop("DATABASE_URL", None)
        repo = Repositorio()
    else:
        if not os.environ.get("DATABASE_URL"):
            print("Falta DATABASE_URL en el .env (o usa --json para el archivo local).")
            return 1
        repo = crear_repositorio()
    informe = aplicar_fase0(repo, hoy_local())
    repo.guardar()
    print("\n".join(informe) if informe else "Nada que hacer: la Fase 0 ya estaba aplicada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
