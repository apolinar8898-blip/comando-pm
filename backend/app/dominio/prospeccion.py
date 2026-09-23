"""Prospección: reglas puras para la base de PyMEs de Querétaro (DENUE).

Normaliza teléfonos y dominios, decide qué establecimientos entran, los agrupa
en empresas (sucursales bajo un mismo empresa_id) y empata directorios externos
(PIQ, CANACINTRA) contra la base. Sin red ni DB: todo se prueba en pruebas/.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from rapidfuzz import fuzz, process

# ---------- Filtros del DENUE ----------

# per_ocu tal cual lo escribe el DENUE → segmento. Lo que no está aquí se excluye
# (0 a 5 y 251 y más personas).
SEGMENTO_POR_ESTRATO = {
    "6 a 10 personas": "micro_plus",
    "11 a 30 personas": "nucleo",
    "31 a 50 personas": "nucleo",
    "51 a 100 personas": "nucleo",
    "101 a 250 personas": "nucleo",
}
ORDEN_ESTRATO = {e: i for i, e in enumerate(SEGMENTO_POR_ESTRATO)}

# Municipios prioritarios (clave INEGI de 3 dígitos).
MUNICIPIOS_PRIORITARIOS = {"014": "Querétaro", "006": "Corregidora", "011": "El Marqués", "016": "San Juan del Río"}

SECTORES_EXCLUIDOS = {"93"}          # gobierno y organismos internacionales (931 y 932)
EXCLUIR_SECTOR_PUBLICO = True        # escuelas, clínicas… "del sector público": no compran a $4,000/mes


def motivo_exclusion(fila: dict) -> Optional[str]:
    """Por qué un renglón del DENUE NO entra a la base (None = entra)."""
    if fila.get("per_ocu") not in SEGMENTO_POR_ESTRATO:
        return "tamaño"
    if (fila.get("codigo_act") or "")[:2] in SECTORES_EXCLUIDOS:
        return "gobierno"
    if EXCLUIR_SECTOR_PUBLICO and "sector público" in (fila.get("nombre_act") or "").lower():
        return "sector_publico"
    return None


# ---------- Normalización ----------

def telefono_e164(texto: str) -> str:
    """Teléfono mexicano a E.164 (+52 + 10 dígitos); '' si no es válido."""
    digitos = re.sub(r"\D", "", texto or "")
    if len(digitos) == 13 and digitos.startswith("521"):   # formato móvil anterior a 2019
        digitos = digitos[3:]
    elif len(digitos) == 12 and digitos.startswith("52"):
        digitos = digitos[2:]
    return f"+52{digitos}" if len(digitos) == 10 else ""


DOMINIOS_GRATIS = {
    "gmail.com", "hotmail.com", "hotmail.es", "outlook.com", "outlook.es", "live.com",
    "live.com.mx", "yahoo.com", "yahoo.com.mx", "yahoo.es", "icloud.com", "me.com",
    "msn.com", "aol.com", "prodigy.net.mx", "prodigy.com.mx", "protonmail.com",
    "proton.me", "gmx.com", "zoho.com", "terra.com.mx", "infinitummail.com",
}


def dominio_de(texto: str) -> str:
    """Dominio limpio de un sitio web o correo: 'WWW.Acme.com.mx/x' → 'acme.com.mx'.
    '' si es un correo gratuito (gmail, hotmail…) o no parece dominio."""
    t = (texto or "").strip().lower()
    if "@" in t:
        t = t.rsplit("@", 1)[1]
    t = re.sub(r"^[a-z]+://", "", t)
    t = t.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].strip(". ")
    if t.startswith("www."):
        t = t[4:]
    if "." not in t or " " in t or t in DOMINIOS_GRATIS:
        return ""
    return t


def normalizar_texto(texto: str) -> str:
    """Mayúsculas, sin acentos ni signos, espacios simples."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r"[^A-Z0-9Ñ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Sufijos societarios ya compactados ("S. A. de C.V." → "SA DE CV"), del más largo al más corto.
_SUFIJOS = [
    "SC DE RL DE CV", "S DE RL DE CV", "SAPI DE CV", "SAB DE CV", "SA DE CV",
    "S DE PR DE RL", "SPR DE RL", "SC DE RL", "S DE RL", "S DE SS", "SAPI", "SAB", "AC", "SC", "SA",
]
_RE_SUFIJOS = re.compile(r"(?:\s(?:" + "|".join(re.escape(s) for s in _SUFIJOS) + r"))+$")


def _compactar_iniciales(texto: str) -> str:
    """Une letras sueltas consecutivas: 'S A DE C V' → 'SA DE CV'."""
    return re.sub(r"\b[A-Z](?: [A-Z]\b)+", lambda m: m.group(0).replace(" ", ""), texto)


def normalizar_razon_social(texto: str) -> str:
    """Razón social comparable: sin sufijos societarios (S.A. de C.V., S. de R.L.…)."""
    t = _compactar_iniciales(normalizar_texto(texto))
    return _RE_SUFIJOS.sub("", " " + t).strip()


# ---------- Establecimientos y empresas ----------

def _limpio(fila: dict, campo: str) -> str:
    return (fila.get(campo) or "").strip()


def _direccion(fila: dict) -> str:
    calle = " ".join(p for p in (_limpio(fila, "tipo_vial"), _limpio(fila, "nom_vial")) if p)
    numero = _limpio(fila, "numero_ext") + _limpio(fila, "letra_ext")
    interior = _limpio(fila, "numero_int") + _limpio(fila, "letra_int")
    partes = [f"{calle} {numero}".strip()]
    if interior:
        partes.append(f"int. {interior}")
    if _limpio(fila, "nom_CenCom"):
        partes.append(_limpio(fila, "nom_CenCom") + (f" local {_limpio(fila, 'num_local')}" if _limpio(fila, "num_local") else ""))
    return ", ".join(p for p in partes if p)


def _numero(texto: str) -> Optional[float]:
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def establecimiento_de_fila(fila: dict, edicion: str = "") -> dict:
    """Renglón del CSV del DENUE → establecimiento normalizado (sin empresa todavía)."""
    return {
        "establecimiento_id": _limpio(fila, "id"),
        "clee": _limpio(fila, "clee"),
        "nom_estab": _limpio(fila, "nom_estab"),
        "raz_social": _limpio(fila, "raz_social"),
        "scian_codigo": _limpio(fila, "codigo_act"),
        "scian_nombre": _limpio(fila, "nombre_act"),
        "per_ocu": _limpio(fila, "per_ocu"),
        "telefono_e164": telefono_e164(fila.get("telefono", "")),
        "correo": _limpio(fila, "correoelec").lower(),
        "www": _limpio(fila, "www").lower(),
        "direccion": _direccion(fila),
        "nom_vial": _limpio(fila, "nom_vial"),
        "colonia": " ".join(p for p in (_limpio(fila, "tipo_asent"), _limpio(fila, "nomb_asent")) if p),
        "cod_postal": _limpio(fila, "cod_postal"),
        "cve_mun": _limpio(fila, "cve_mun").zfill(3),
        "municipio": _limpio(fila, "municipio"),
        "localidad": _limpio(fila, "localidad"),
        "latitud": _numero(fila.get("latitud")),
        "longitud": _numero(fila.get("longitud")),
        "fecha_alta": _limpio(fila, "fecha_alta"),
        "edicion_denue": edicion,
    }


def claves_duplicado(e: dict) -> list[str]:
    """Llaves que, si dos establecimientos comparten alguna, los hacen la misma empresa:
    mismo teléfono, mismo dominio propio, o misma razón social + misma calle."""
    claves = []
    if e["telefono_e164"]:
        claves.append("tel:" + e["telefono_e164"])
    dominio = dominio_de(e["www"]) or dominio_de(e["correo"])
    if dominio:
        claves.append("dom:" + dominio)
    razon = normalizar_razon_social(e["raz_social"])
    calle = normalizar_texto(e.get("nom_vial", ""))
    if razon and calle:
        claves.append(f"rs:{razon}|{calle}")
    return claves


def _prioridad_representante(e: dict) -> tuple:
    """El representante de la empresa: el de más personal, con teléfono, con web, id menor."""
    return (-ORDEN_ESTRATO.get(e["per_ocu"], -1), not e["telefono_e164"], not e["www"], int(e["establecimiento_id"] or 0))


def agrupar_empresas(establecimientos: list[dict], empresa_previa: Optional[dict[str, str]] = None) -> list[dict]:
    """Agrupa establecimientos en empresas (union-find sobre claves_duplicado).

    empresa_previa: {establecimiento_id: empresa_id} de una carga anterior; si un
    grupo ya tenía empresa_id se conserva (no se rompe el vínculo con el CRM).
    Devuelve empresas con la lista 'establecimientos' (ids) y a cada
    establecimiento le escribe su 'empresa_id'.
    """
    empresa_previa = empresa_previa or {}
    padre = list(range(len(establecimientos)))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    primero_con_clave: dict[str, int] = {}
    for i, e in enumerate(establecimientos):
        for clave in claves_duplicado(e):
            if clave in primero_con_clave:
                a, b = raiz(i), raiz(primero_con_clave[clave])
                if a != b:
                    padre[a] = b
            else:
                primero_con_clave[clave] = i

    grupos: dict[int, list[dict]] = {}
    for i, e in enumerate(establecimientos):
        grupos.setdefault(raiz(i), []).append(e)

    empresas = []
    for miembros in grupos.values():
        miembros.sort(key=_prioridad_representante)
        rep = miembros[0]
        previos = sorted({empresa_previa[m["establecimiento_id"]] for m in miembros if m["establecimiento_id"] in empresa_previa})
        empresa_id = previos[0] if previos else "denue:" + rep["establecimiento_id"]
        for m in miembros:
            m["empresa_id"] = empresa_id

        def primero(campo: str, filtro=lambda v: v) -> str:
            return next((m[campo] for m in miembros if filtro(m[campo])), "")

        telefono = primero("telefono_e164")
        correo = primero("correo")
        sitio = primero("www", lambda v: bool(dominio_de(v))) or primero("www")
        dominio = next((d for m in miembros for d in (dominio_de(m["www"]), dominio_de(m["correo"])) if d), "")
        scian = rep["scian_codigo"]
        empresas.append({
            "empresa_id": empresa_id,
            "nombre_comercial": rep["nom_estab"] or rep["raz_social"],
            "razon_social": primero("raz_social"),
            "dominio": dominio,
            "sitio_web": sitio,
            "scian_codigo": scian,
            "scian_nombre": rep["scian_nombre"],
            "sector": scian[:2],
            "estrato": rep["per_ocu"],
            "segmento": SEGMENTO_POR_ESTRATO[rep["per_ocu"]],
            "es_asociacion": scian.startswith("813"),
            "cve_mun": rep["cve_mun"],
            "municipio": rep["municipio"],
            "num_establecimientos": len(miembros),
            "telefono_principal": telefono,
            "fuente_telefono": "denue" if telefono else "",
            "correo_generico": correo,
            "fuente_correo": "denue" if correo else "",
            "edicion_denue": rep["edicion_denue"],
            "establecimientos": [m["establecimiento_id"] for m in miembros],
        })
    return empresas


# ---------- Directorios externos (PIQ, CANACINTRA…) ----------

UMBRAL_EMPATE = 90      # ≥ 90: empatado automático
UMBRAL_REVISION = 75    # 75–89: cola de revisión manual (estado 'pendiente')

# Palabras que no distinguen a una empresa: sin quitarlas, "RONAL QUERETARO" y
# "REGIONAL QUERETARO" se parecen 91 %.
_GENERICAS = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "THE", "AND", "QUERETARO", "QRO",
              "MEXICO", "MEXICANA", "MEXICANO", "MX", "GRUPO", "GROUP", "CORP", "CORPORATION", "COMPANY"}


def clave_empate(nombre_normalizado: str) -> str:
    return " ".join(p for p in nombre_normalizado.split() if p not in _GENERICAS)


def empatar(registro: dict, candidatos: list[dict], cve_mun: Optional[str] = None) -> dict:
    """Busca la empresa de la base que corresponde a un registro de directorio.

    registro: {'nombre', 'telefono'} (teléfono ya en E.164 o '').
    candidatos: [{'empresa_id', 'cve_mun', 'telefonos': set, 'nombres': [str normalizados]}].
    Primero por teléfono exacto (confianza 100); si no, por nombre/razón social
    normalizados (rapidfuzz), restringido al municipio si se da.
    """
    tel = registro.get("telefono") or ""
    if tel:
        por_tel = {c["empresa_id"] for c in candidatos if tel in c["telefonos"]}
        if len(por_tel) == 1:
            return {"empresa_id": por_tel.pop(), "confianza": 100.0, "metodo": "telefono", "estado": "empatado"}

    nombre = clave_empate(normalizar_razon_social(registro.get("nombre", "")))
    if not nombre:
        return {"empresa_id": None, "confianza": 0.0, "metodo": "", "estado": "sin_match"}
    opciones = {}
    for c in candidatos:
        if cve_mun and c["cve_mun"] != cve_mun:
            continue
        for n in c["nombres"]:
            clave = clave_empate(n)
            if clave:
                opciones.setdefault(clave, c["empresa_id"])
    mejor = process.extractOne(nombre, list(opciones), scorer=fuzz.token_sort_ratio) if opciones else None
    if not mejor or mejor[1] < UMBRAL_REVISION:
        return {"empresa_id": None, "confianza": round(mejor[1], 1) if mejor else 0.0, "metodo": "nombre", "estado": "sin_match"}
    estado = "empatado" if mejor[1] >= UMBRAL_EMPATE else "pendiente"
    return {"empresa_id": opciones[mejor[0]], "confianza": round(mejor[1], 1), "metodo": "nombre", "estado": estado}


def nombres_candidato(establecimientos: Iterable[dict]) -> list[str]:
    """Nombres comparables de una empresa: nombre comercial y razón social de cada sucursal."""
    vistos = []
    for e in establecimientos:
        for n in (normalizar_razon_social(e.get("nom_estab", "")), normalizar_razon_social(e.get("raz_social", ""))):
            if n and n not in vistos:
                vistos.append(n)
    return vistos
