"""Tests de la base de prospección (reglas puras: normalización, filtros, deduplicación, empate)."""
from app.dominio.prospeccion import (
    agrupar_empresas,
    claves_duplicado,
    dominio_de,
    empatar,
    establecimiento_de_fila,
    motivo_exclusion,
    nombres_candidato,
    normalizar_razon_social,
    telefono_e164,
)


def fila(**kw) -> dict:
    """Renglón del CSV del DENUE con valores por defecto razonables."""
    base = {
        "id": "100", "clee": "", "nom_estab": "TALLER EL GÜERO", "raz_social": "", "codigo_act": "811111",
        "nombre_act": "Reparación mecánica en general de automóviles y camiones", "per_ocu": "11 a 30 personas",
        "tipo_vial": "AVENIDA", "nom_vial": "CONSTITUYENTES", "numero_ext": "10", "letra_ext": "",
        "numero_int": "", "letra_int": "", "nom_CenCom": "", "num_local": "", "tipo_asent": "COLONIA",
        "nomb_asent": "CENTRO", "cod_postal": "76000", "cve_mun": "14", "municipio": "Querétaro",
        "localidad": "Santiago de Querétaro   ", "telefono": "", "correoelec": "", "www": "",
        "latitud": "20.59", "longitud": "-100.39", "fecha_alta": "2019-11",
    }
    base.update(kw)
    return base


def est(**kw) -> dict:
    return establecimiento_de_fila(fila(**kw), "05_2026")


# ---------- Normalización ----------

def test_telefono_e164():
    assert telefono_e164("442 628 4193") == "+524426284193"
    assert telefono_e164("(442) 628-41-93") == "+524426284193"
    assert telefono_e164("+52 442 628 4193") == "+524426284193"
    assert telefono_e164("521 442 628 4193") == "+524426284193"   # prefijo móvil viejo
    assert telefono_e164("22120550") == ""                        # 8 dígitos: no es válido
    assert telefono_e164("") == ""


def test_dominio_propio_y_gratuitos():
    assert dominio_de("WWW.ACME.COM.MX") == "acme.com.mx"
    assert dominio_de("https://www.acme.com/contacto?x=1") == "acme.com"
    assert dominio_de("VENTAS@ACME.COM.MX") == "acme.com.mx"
    assert dominio_de("taller@gmail.com") == ""
    assert dominio_de("x@HOTMAIL.COM") == ""
    assert dominio_de("contacto@prodigy.net.mx") == ""
    assert dominio_de("no tengo") == ""


def test_razon_social_sin_sufijos():
    assert normalizar_razon_social("ABINSA, S. A. DE C.V.") == "ABINSA"
    assert normalizar_razon_social("Corrugados de Baja California, S. de R.L. de C.V.") == "CORRUGADOS DE BAJA CALIFORNIA"
    assert normalizar_razon_social("Válvulas de Precisión, S.A.P.I. de C.V.") == "VALVULAS DE PRECISION"
    assert normalizar_razon_social("Colegio Montessori A.C.") == "COLEGIO MONTESSORI"


# ---------- Filtros ----------

def test_filtros_de_tamano_y_sector():
    assert motivo_exclusion(fila()) is None
    assert motivo_exclusion(fila(per_ocu="6 a 10 personas")) is None
    assert motivo_exclusion(fila(per_ocu="0 a 5 personas")) == "tamaño"
    assert motivo_exclusion(fila(per_ocu="251 y más personas")) == "tamaño"
    assert motivo_exclusion(fila(codigo_act="931210")) == "gobierno"
    assert motivo_exclusion(fila(codigo_act="611112", nombre_act="Escuelas de educación primaria del sector público")) == "sector_publico"
    # Asociaciones (813) se marcan, no se excluyen.
    assert motivo_exclusion(fila(codigo_act="813210", nombre_act="Asociaciones y organizaciones religiosas")) is None


def test_establecimiento_normalizado():
    e = est(telefono="442 111 2233", correoelec="VENTAS@ACME.COM", cve_mun="6")
    assert e["telefono_e164"] == "+524421112233"
    assert e["correo"] == "ventas@acme.com"
    assert e["cve_mun"] == "006"
    assert e["localidad"] == "Santiago de Querétaro"
    assert e["direccion"] == "AVENIDA CONSTITUYENTES 10"
    assert e["latitud"] == 20.59


# ---------- Deduplicación ----------

def test_mismo_telefono_es_la_misma_empresa():
    a = est(id="1", telefono="4421112233", nom_estab="ACME CENTRO")
    b = est(id="2", telefono="442-111-2233", nom_estab="ACME NORTE", per_ocu="31 a 50 personas")
    c = est(id="3", telefono="4429998877", nom_estab="OTRO NEGOCIO")
    empresas = agrupar_empresas([a, b, c])
    assert len(empresas) == 2
    acme = next(e for e in empresas if e["num_establecimientos"] == 2)
    # Representante = la sucursal con más personal.
    assert acme["empresa_id"] == "denue:2"
    assert acme["nombre_comercial"] == "ACME NORTE"
    assert acme["estrato"] == "31 a 50 personas"
    assert a["empresa_id"] == b["empresa_id"] == "denue:2"


def test_mismo_dominio_une_y_correo_gratuito_no():
    a = est(id="1", www="www.acme.com.mx")
    b = est(id="2", correoelec="ventas@acme.com.mx")
    c = est(id="3", correoelec="uno@gmail.com")
    d = est(id="4", correoelec="dos@gmail.com")
    empresas = agrupar_empresas([a, b, c, d])
    assert sorted(e["num_establecimientos"] for e in empresas) == [1, 1, 2]
    assert next(e for e in empresas if e["num_establecimientos"] == 2)["dominio"] == "acme.com.mx"


def test_razon_social_y_calle():
    a = est(id="1", raz_social="Industrias Cazel, S. de R.L. de C.V.", nom_vial="LA NORIA")
    b = est(id="2", raz_social="INDUSTRIAS CAZEL SA DE CV", nom_vial="La Noria")
    c = est(id="3", raz_social="INDUSTRIAS CAZEL SA DE CV", nom_vial="OTRA CALLE")
    empresas = agrupar_empresas([a, b, c])
    assert sorted(e["num_establecimientos"] for e in empresas) == [1, 2]
    # Sin razón social no hay llave rs: (persona física).
    assert not any(k.startswith("rs:") for k in claves_duplicado(est(raz_social="")))


def test_union_transitiva():
    # a–b por teléfono, b–c por dominio → las tres son una empresa.
    a = est(id="1", telefono="4421112233")
    b = est(id="2", telefono="4421112233", www="acme.com")
    c = est(id="3", correoelec="x@acme.com")
    assert len(agrupar_empresas([a, b, c])) == 1


def test_recarga_conserva_empresa_id():
    # En la carga anterior la empresa era "denue:1"; ahora el representante sería el 2.
    a = est(id="1", telefono="4421112233")
    b = est(id="2", telefono="4421112233", per_ocu="51 a 100 personas")
    empresas = agrupar_empresas([a, b], {"1": "denue:1"})
    assert empresas[0]["empresa_id"] == "denue:1"


def test_segmento_y_asociacion():
    micro = agrupar_empresas([est(id="1", per_ocu="6 a 10 personas")])[0]
    assert micro["segmento"] == "micro_plus"
    asoc = agrupar_empresas([est(id="2", codigo_act="813210")])[0]
    assert asoc["es_asociacion"] and asoc["segmento"] == "nucleo"


# ---------- Empate con directorios ----------

CANDIDATOS = [
    {"empresa_id": "denue:1", "cve_mun": "014", "telefonos": {"+524422272850"},
     "nombres": nombres_candidato([{"nom_estab": "AERNNOVA", "raz_social": "AERNNOVA COMPONENTES MEXICO SA DE CV"}])},
    {"empresa_id": "denue:2", "cve_mun": "014", "telefonos": set(),
     "nombres": nombres_candidato([{"nom_estab": "REGIONAL QUERETARO", "raz_social": ""}])},
    {"empresa_id": "denue:3", "cve_mun": "016", "telefonos": set(),
     "nombres": nombres_candidato([{"nom_estab": "COPPER CLAD", "raz_social": "COPPER CLAD SA DE CV"}])},
]


def test_empate_por_telefono():
    m = empatar({"nombre": "Otro nombre", "telefono": "+524422272850"}, CANDIDATOS)
    assert (m["empresa_id"], m["metodo"], m["estado"]) == ("denue:1", "telefono", "empatado")


def test_empate_por_nombre_sin_sufijos():
    m = empatar({"nombre": "AERNNOVA COMPONENTES MEXICO, S.A. DE C.V.", "telefono": ""}, CANDIDATOS, "014")
    assert m["empresa_id"] == "denue:1" and m["estado"] == "empatado"


def test_palabras_genericas_no_empatan():
    # "RONAL QUERETARO" ≠ "REGIONAL QUERETARO": sin 'QUERETARO' ya no se parecen tanto.
    m = empatar({"nombre": "RONAL QUERETARO S.A. DE C.V.", "telefono": ""}, CANDIDATOS, "014")
    assert m["estado"] != "empatado"


def test_empate_respeta_municipio():
    m = empatar({"nombre": "COPPER CLAD, S.A. DE C.V.", "telefono": ""}, CANDIDATOS, "014")
    assert m["estado"] == "sin_match"
    assert empatar({"nombre": "COPPER CLAD, S.A. DE C.V.", "telefono": ""}, CANDIDATOS)["empresa_id"] == "denue:3"
