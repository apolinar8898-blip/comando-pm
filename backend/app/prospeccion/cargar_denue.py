r"""Carga el DENUE de Querétaro (descarga masiva de INEGI) a las tablas pq_*.

Uso (desde la carpeta backend):
    .venv\Scripts\python -m app.prospeccion.cargar_denue            # descarga y carga
    .venv\Scripts\python -m app.prospeccion.cargar_denue --simular  # solo muestra el resumen
    .venv\Scripts\python -m app.prospeccion.cargar_denue --zip C:\ruta\denue_22_csv.zip

No usa token ni cuota: es un solo archivo público. Se puede correr de nuevo con
cada edición del DENUE: actualiza lo que viene del DENUE, conserva lo tuyo
(score, CRM, opt_out…) y marca vigente=false lo que ya no aparece (nada se borra).
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

from ..dominio.prospeccion import (
    MUNICIPIOS_PRIORITARIOS, agrupar_empresas, establecimiento_de_fila, motivo_exclusion,
)
from .base import DATOS, cargar_env, conectar, preparar_consola

URL_DENUE = "https://www.inegi.org.mx/contenidos/masiva/denue/denue_22_csv.zip"
CSV_EN_ZIP = "conjunto_de_datos/denue_inegi_22_.csv"

COLUMNAS_EMPRESA = [
    "empresa_id", "nombre_comercial", "razon_social", "dominio", "sitio_web", "scian_codigo",
    "scian_nombre", "sector", "estrato", "segmento", "es_asociacion", "cve_mun", "municipio",
    "num_establecimientos", "telefono_principal", "fuente_telefono", "correo_generico",
    "fuente_correo", "edicion_denue",
]
COLUMNAS_ESTABLECIMIENTO = [
    "establecimiento_id", "empresa_id", "clee", "nom_estab", "raz_social", "scian_codigo",
    "per_ocu", "telefono_e164", "correo", "www", "direccion", "colonia", "cod_postal",
    "cve_mun", "municipio", "localidad", "latitud", "longitud", "fecha_alta", "edicion_denue",
]


def descargar(destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"⬇️  Descargando {URL_DENUE} …")
    peticion = urllib.request.Request(URL_DENUE, headers={"User-Agent": "ComandoPM-prospeccion/1.0"})
    with urllib.request.urlopen(peticion, timeout=120) as r, open(destino, "wb") as f:
        f.write(r.read())
    print(f"   {destino.stat().st_size / 1e6:.1f} MB en {destino}")
    return destino


def leer_zip(ruta: Path) -> tuple[list[dict], Counter, str]:
    """Establecimientos que entran, conteo de excluidos por motivo y edición ('05_2026')."""
    with zipfile.ZipFile(ruta) as z:
        meta = z.read("metadatos/metadatos_denue.txt").decode("utf-8-sig", errors="replace")
        edicion = (re.search(r"\(DENUE\)\s*(\d{2}_\d{4})", meta) or re.search(r"(\d{2}_\d{4})", meta))
        edicion = edicion.group(1) if edicion else ""
        # El CSV viene en cp1252 (no UTF-8), entrecomillado y con CRLF.
        with io.TextIOWrapper(z.open(CSV_EN_ZIP), encoding="cp1252", newline="") as f:
            excluidos: Counter = Counter()
            entran = []
            for fila in csv.DictReader(f):
                motivo = motivo_exclusion(fila)
                if motivo:
                    excluidos[motivo] += 1
                else:
                    entran.append(establecimiento_de_fila(fila, edicion))
    return entran, excluidos, edicion


def empresa_previa(con) -> dict[str, str]:
    return dict(con.execute("select establecimiento_id, empresa_id from pq_establecimientos").fetchall())


def guardar(con, empresas: list[dict], establecimientos: list[dict]) -> None:
    """Todo en UNA transacción: tablas temporales por COPY y luego upsert."""
    with con.transaction():
        con.execute("create temp table t_emp (like pq_empresas including defaults) on commit drop")
        con.execute("create temp table t_est (like pq_establecimientos including defaults) on commit drop")
        with con.cursor() as cur:
            with cur.copy(f"copy t_emp ({', '.join(COLUMNAS_EMPRESA)}) from stdin") as copia:
                for e in empresas:
                    copia.write_row([e[c] for c in COLUMNAS_EMPRESA])
            with cur.copy(f"copy t_est ({', '.join(COLUMNAS_ESTABLECIMIENTO)}) from stdin") as copia:
                for e in establecimientos:
                    copia.write_row([e[c] for c in COLUMNAS_ESTABLECIMIENTO])

        # Solo se pisan columnas que vienen del DENUE; score, CRM, opt_out, resumen,
        # directorios y lo enriquecido (web/Apollo) se conservan.
        actualizar = [c for c in COLUMNAS_EMPRESA if c not in ("empresa_id", "telefono_principal", "fuente_telefono",
                                                              "correo_generico", "fuente_correo", "dominio", "sitio_web")]
        sets = ", ".join(f"{c} = excluded.{c}" for c in actualizar)
        # Contacto: el del DENUE solo si la empresa no tiene uno de otra fuente.
        for campo, fuente in (("telefono_principal", "fuente_telefono"), ("correo_generico", "fuente_correo")):
            sets += (f", {campo} = case when pq_empresas.{fuente} in ('', 'denue') then excluded.{campo} else pq_empresas.{campo} end"
                     f", {fuente} = case when pq_empresas.{fuente} in ('', 'denue') then excluded.{fuente} else pq_empresas.{fuente} end")
        sets += ", dominio = coalesce(nullif(pq_empresas.dominio, ''), excluded.dominio)"
        sets += ", sitio_web = coalesce(nullif(pq_empresas.sitio_web, ''), excluded.sitio_web)"
        con.execute(f"""
            insert into pq_empresas ({', '.join(COLUMNAS_EMPRESA)}, vigente, actualizado)
            select {', '.join(COLUMNAS_EMPRESA)}, true, now() from t_emp
            on conflict (empresa_id) do update set {sets}, vigente = true, actualizado = now()
        """)
        sets_est = ", ".join(f"{c} = excluded.{c}" for c in COLUMNAS_ESTABLECIMIENTO if c != "establecimiento_id")
        con.execute(f"""
            insert into pq_establecimientos ({', '.join(COLUMNAS_ESTABLECIMIENTO)}, vigente, actualizado)
            select {', '.join(COLUMNAS_ESTABLECIMIENTO)}, true, now() from t_est
            on conflict (establecimiento_id) do update set {sets_est}, vigente = true, actualizado = now()
        """)
        # Lo que ya no está en esta edición: se marca, no se borra.
        con.execute("""update pq_establecimientos set vigente = false, actualizado = now()
                       where vigente and establecimiento_id not in (select establecimiento_id from t_est)""")
        con.execute("""update pq_empresas set vigente = false, actualizado = now()
                       where vigente and empresa_id not in (select empresa_id from t_emp)""")


def imprimir_resumen(empresas: list[dict], establecimientos: list[dict], excluidos: Counter, edicion: str) -> None:
    n = len(empresas)
    pct = lambda k: f"{k:,} ({k / n:.0%})" if n else "0"
    print(f"\n📊 DENUE {edicion} — Querétaro")
    print(f"   Establecimientos que entran: {len(establecimientos):,}")
    print(f"   Excluidos: " + ", ".join(f"{m} {c:,}" for m, c in excluidos.most_common()))
    print(f"   Empresas (tras agrupar sucursales/duplicados): {n:,}")
    print(f"   Con varias sucursales: {sum(e['num_establecimientos'] > 1 for e in empresas):,}")
    print(f"   Con teléfono: {pct(sum(bool(e['telefono_principal']) for e in empresas))}")
    print(f"   Con dominio propio: {pct(sum(bool(e['dominio']) for e in empresas))}")
    print(f"   Con correo: {pct(sum(bool(e['correo_generico']) for e in empresas))}")
    print("\n   Por segmento / estrato:")
    for (s, est), c in sorted(Counter((e["segmento"], e["estrato"]) for e in empresas).items()):
        print(f"     {s:<11} {est:<20} {c:>6,}")
    print("\n   Por municipio (★ = prioritario):")
    for (cve, mun), c in Counter((e["cve_mun"], e["municipio"]) for e in empresas).most_common():
        print(f"     {'★' if cve in MUNICIPIOS_PRIORITARIOS else ' '} {mun:<24} {c:>6,}")
    print("\n   Top sectores SCIAN (2 dígitos):")
    for s, c in Counter(e["sector"] for e in empresas).most_common(10):
        print(f"     {s}  {c:>6,}")


def main() -> int:
    preparar_consola()
    parser = argparse.ArgumentParser(description="Carga el DENUE de Querétaro a Supabase.")
    parser.add_argument("--zip", type=Path, help="usar un zip ya descargado")
    parser.add_argument("--simular", action="store_true", help="no escribe en la DB; solo resume")
    args = parser.parse_args()
    cargar_env()

    ruta = args.zip or descargar(DATOS / "denue_22_csv.zip")
    establecimientos, excluidos, edicion = leer_zip(ruta)

    if args.simular:
        empresas = agrupar_empresas(establecimientos)
        imprimir_resumen(empresas, establecimientos, excluidos, edicion)
        print("\n(simulación: no se escribió nada)")
        return 0

    with conectar() as con:
        empresas = agrupar_empresas(establecimientos, empresa_previa(con))
        guardar(con, empresas, establecimientos)
        total = con.execute("select count(*) from pq_empresas where vigente").fetchone()[0]
    imprimir_resumen(empresas, establecimientos, excluidos, edicion)
    print(f"\n✅ Guardado en Supabase: {total:,} empresas vigentes. Créditos de API consumidos: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
