r"""Importa el directorio público del Parque Industrial Querétaro (PIQ, 2024) y lo cruza con el DENUE.

Uso (desde la carpeta backend, después de cargar_denue):
    .venv\Scripts\python -m app.prospeccion.importar_piq
    .venv\Scripts\python -m app.prospeccion.importar_piq --pdf C:\ruta\DIRECTORIO_EMPRESAS_PIQ_2024.pdf

Las empresas empatadas quedan con directorios = {piq_2024}. Las dudosas van a
pq_directorio con estado 'pendiente' (revisión manual). Muchas del PIQ tienen
más de 250 empleados: esas no están en la base (quedan 'sin_match').
"""
from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

from ..dominio.prospeccion import telefono_e164
from .base import DATOS, cargar_env, conectar, preparar_consola
from .directorios import importar

URL_PIQ = "https://piq.com.mx/files/DIRECTORIO_EMPRESAS_PIQ_2024.pdf"
FUENTE = "piq_2024"
MUNICIPIO_PIQ = "014"   # el PIQ está en el municipio de Querétaro


def descargar(destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    peticion = urllib.request.Request(URL_PIQ, headers={"User-Agent": "ComandoPM-prospeccion/1.0"})
    with urllib.request.urlopen(peticion, timeout=60) as r, open(destino, "wb") as f:
        f.write(r.read())
    return destino


def _celda(valor) -> str:
    return re.sub(r"\s+", " ", valor or "").strip()


def leer_pdf(ruta: Path) -> list[dict]:
    """Tablas del PDF → registros. Columnas: EMPRESA, Nacionalidad, Giro, Conmutador, Dirección."""
    import pdfplumber

    registros, vistos = [], set()
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                for fila in tabla:
                    celdas = [_celda(c) for c in fila] + [""] * 5
                    nombre, nacionalidad, giro, conmutador, direccion = celdas[:5]
                    if not nombre or nombre.upper() == "EMPRESA" or nombre in vistos:
                        continue
                    vistos.add(nombre)
                    # "446 139 5762/446 139 5648" → el primero.
                    telefono = telefono_e164(conmutador.split("/")[0])
                    registros.append({
                        "nombre": nombre, "giro": giro, "telefono": telefono, "direccion": direccion,
                        "datos": {"nacionalidad": nacionalidad, "conmutador": conmutador},
                    })
    return registros


def main() -> int:
    preparar_consola()
    parser = argparse.ArgumentParser(description="Importa el directorio del PIQ y lo cruza con la base DENUE.")
    parser.add_argument("--pdf", type=Path, help="usar un PDF ya descargado")
    args = parser.parse_args()
    cargar_env()

    ruta = args.pdf or descargar(DATOS / "DIRECTORIO_EMPRESAS_PIQ_2024.pdf")
    registros = leer_pdf(ruta)
    print(f"📄 PIQ 2024: {len(registros)} empresas en el directorio")
    with conectar() as con:
        conteo = importar(con, FUENTE, registros, MUNICIPIO_PIQ)
    print(f"   Empatadas con la base: {conteo['empatado']}")
    print(f"   Para revisión manual (pendiente): {conteo['pendiente']}")
    print(f"   Sin match (probablemente > 250 empleados o fuera del DENUE): {conteo['sin_match']}")
    print("✅ Listo. Créditos de API consumidos: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
