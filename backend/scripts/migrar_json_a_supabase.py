r"""Copia tus datos del archivo JSON a Supabase (una sola vez).

Uso (desde la carpeta backend):
    .venv\Scripts\python scripts\migrar_json_a_supabase.py
    .venv\Scripts\python scripts\migrar_json_a_supabase.py --forzar   # si Supabase ya tiene datos

Requiere DATABASE_URL en el .env de la raíz del repo (Session pooler de Supabase).
Al terminar relee Supabase y compara los conteos con el JSON.
"""
from __future__ import annotations

import os
import sys

from _entorno import cargar_env

from app.repositorio import Repositorio
from app.repositorio_supabase import TABLAS, RepositorioSupabase


def conteos(repo) -> dict[str, int]:
    volcado = repo.volcado()
    return {s["coleccion"]: len(volcado[s["coleccion"]]) for s in TABLAS}


def main() -> int:
    cargar_env()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Falta DATABASE_URL en el archivo .env de la raíz (ver .env.example).")
        return 1

    origen = Repositorio()
    print(f"Origen JSON: {origen.ruta}")
    print("  ", conteos(origen))

    destino = RepositorioSupabase(dsn)
    if not destino.vacio() and "--forzar" not in sys.argv:
        print("Supabase ya tiene proyectos. No piso nada; usa --forzar si de verdad quieres sobrescribir.")
        return 1

    for spec in TABLAS:
        setattr(destino, spec["coleccion"], getattr(origen, spec["coleccion"]))
    destino.guardar()

    verificacion = RepositorioSupabase(dsn)
    esperado, obtenido = conteos(origen), conteos(verificacion)
    print("Supabase:", obtenido)
    if esperado != obtenido:
        print("❌ Los conteos NO coinciden. Revisa antes de seguir.")
        return 1
    print("✅ Migración completa: los conteos coinciden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
