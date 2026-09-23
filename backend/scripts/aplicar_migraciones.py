r"""Aplica en Supabase las migraciones de migraciones/ que falten (en orden).

Uso (desde la carpeta backend):
    .venv\Scripts\python scripts\aplicar_migraciones.py

Lee la tabla "migraciones" para saber cuáles ya están; cada archivo corre en
su propia transacción (si falla, no queda a medias). Requiere DATABASE_URL.
"""
from __future__ import annotations

import os
import re
import sys

from _entorno import RAIZ, cargar_env


def main() -> int:
    cargar_env()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Falta DATABASE_URL en el .env de la raíz.")
        return 1
    import psycopg

    from app.repositorio_supabase import limpiar_dsn

    archivos = sorted((RAIZ / "migraciones").glob("[0-9][0-9][0-9]_*.sql"))
    with psycopg.connect(limpiar_dsn(dsn), prepare_threshold=None, connect_timeout=15) as con:
        aplicadas = {n for (n,) in con.execute("select numero from migraciones").fetchall()}
        pendientes = [a for a in archivos if int(re.match(r"(\d+)", a.name).group(1)) not in aplicadas]
        if not pendientes:
            print("✅ No hay migraciones pendientes.")
            return 0
        for archivo in pendientes:
            with con.transaction():
                con.execute(archivo.read_text(encoding="utf-8"))
            print(f"✅ aplicada {archivo.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
