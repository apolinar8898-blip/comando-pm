"""Tests de la Fase 1: Captación SINPROTEK (reglas puras + API + Alex)."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.dominio import acciones_prospeccion, componer_plan
from app.dominio.captacion import (
    alertas,
    cambiar_etapa,
    conversion,
    etapa_maxima,
    kpis_captacion,
    montos_por_segmento,
    normalizar_telefono,
    peor,
    ritmo_semanal,
    salud_captacion,
    tarea_de_accion,
)
from app.main import crear_app
from app.modelos import Interaccion, Prospecto, Tarea
from app.reloj import hoy_local
from app.repositorio import Repositorio
from app.semilla_real import aplicar_fase0

MIERCOLES = date(2026, 9, 23)


def prospecto(**kw) -> Prospecto:
    base = dict(empresa="Tornillos del Bajío", creado=datetime(2026, 9, 22, 9, 0))
    base.update(kw)
    return Prospecto(**base)


def interaccion(p: Prospecto, fecha: date) -> Interaccion:
    return Interaccion(prospecto_id=p.id, canal="llamada", fecha=datetime.combine(fecha, datetime.min.time()))


# ---------- Montos y etapas ----------

def test_montos_precargados_por_segmento():
    assert montos_por_segmento("pyme") == (4000, 4000)
    assert montos_por_segmento("independiente") == (3000, 3500)


def test_perdido_exige_motivo():
    p = prospecto(etapa="contactado")
    with pytest.raises(ValueError):
        cambiar_etapa(p, "perdido", MIERCOLES)
    perdido = cambiar_etapa(p, "perdido", MIERCOLES, "Ya tiene proveedor")
    assert perdido.motivo_perdida == "Ya tiene proveedor"


def test_cambiar_etapa_registra_solo_la_primera_entrada():
    p = cambiar_etapa(prospecto(), "contactado", MIERCOLES)
    p = cambiar_etapa(p, "identificado", MIERCOLES + timedelta(days=1))
    p = cambiar_etapa(p, "contactado", MIERCOLES + timedelta(days=5))
    assert p.fechas_etapa["contactado"] == MIERCOLES.isoformat()


def test_conversion_cuenta_la_etapa_mas_alta_alcanzada_aunque_se_pierda():
    a = prospecto(fechas_etapa={"demo_hecha": "2026-09-01"}, etapa="perdido", motivo_perdida="precio")
    b = prospecto(etapa="contactado")
    c = prospecto(etapa="identificado")
    assert etapa_maxima(a) == 3
    filas = {f["de"]: f for f in conversion([a, b, c])}
    assert filas["identificado"]["llegaron"] == 3 and filas["identificado"]["pasaron"] == 2
    assert filas["contactado"]["pct"] == 50.0
    assert filas["negociacion"]["llegaron"] == 0 and filas["negociacion"]["pct"] is None


# ---------- Alertas ----------

def test_alerta_por_accion_vencida_y_por_mas_de_7_dias_sin_contacto():
    p = prospecto(fecha_proxima_accion=MIERCOLES - timedelta(days=1))
    assert "accion_vencida" in alertas(p, [], MIERCOLES)

    reciente = prospecto()
    assert alertas(reciente, [interaccion(reciente, MIERCOLES - timedelta(days=7))], MIERCOLES) == []
    assert alertas(reciente, [interaccion(reciente, MIERCOLES - timedelta(days=8))], MIERCOLES) == ["sin_contacto"]
    # Sin interacciones cuenta desde el alta
    viejo = prospecto(creado=datetime(2026, 9, 1))
    assert alertas(viejo, [], MIERCOLES) == ["sin_contacto"]
    # Cerrados no alertan
    assert alertas(prospecto(etapa="ganado", creado=datetime(2026, 1, 1)), [], MIERCOLES) == []


def test_telefono_normalizado_a_10_digitos():
    assert normalizar_telefono("+52 1 (442) 123-4567") == "4421234567"
    assert normalizar_telefono("442 123 4567") == "4421234567"


# ---------- KPIs, ritmo y salud ----------

def test_ritmo_prorrateado_no_castiga_el_lunes():
    assert ritmo_semanal(0, 25, date(2026, 9, 21)) is None          # lunes
    assert ritmo_semanal(5, 25, date(2026, 9, 22)) == pytest.approx(1.0)  # martes: 1 día hábil hecho
    assert ritmo_semanal(10, 25, date(2026, 9, 27)) == pytest.approx(0.4)  # domingo: semana completa


def test_kpis_mrr_ganados_y_ponderado():
    ganado = prospecto(etapa="ganado", monto_mensual=4000)
    demo = prospecto(etapa="demo_hecha", monto_mensual=4000)
    perdido = prospecto(etapa="perdido", motivo_perdida="x", monto_mensual=4000)
    k = kpis_captacion([ganado, demo, perdido], [interaccion(demo, MIERCOLES)], MIERCOLES, 25)
    assert k["ganados"] == 1 and k["meta_clientes"] == 3
    assert k["mrr_actual"] == 4000
    assert k["mrr_ponderado"] == pytest.approx(4000 * 0.35)
    assert k["dias_restantes"] == (date(2026, 12, 31) - MIERCOLES).days
    assert k["interacciones_semana"] == 1
    assert k["por_etapa"]["perdido"] == 1


def test_salud_roja_por_prospectos_sin_contacto_o_ritmo_bajo():
    viejos = [prospecto(creado=datetime(2026, 9, 1)) for _ in range(4)]
    base = kpis_captacion(viejos[:3], [], MIERCOLES, 25)
    base["ritmo"] = None
    assert salud_captacion(base) == "verde"   # 3 sin contacto: aún tolerable
    assert salud_captacion({**base, "sin_contacto": 4}) == "rojo"
    assert salud_captacion({**base, "ritmo": 0.49}) == "rojo"
    assert salud_captacion({**base, "ritmo": 0.5}) == "verde"
    assert peor("amarillo", "rojo") == "rojo" and peor("amarillo", "verde") == "amarillo"


# ---------- Ivy Lee ----------

def test_acciones_de_prospeccion_van_antes_que_todo():
    p = prospecto(fecha_proxima_accion=MIERCOLES - timedelta(days=2), proxima_accion="Llamar")
    accion = tarea_de_accion(p, None, "sin")
    futura = accion.model_copy(update={"id": "futura", "fecha_inicio": MIERCOLES + timedelta(days=1),
                                       "fecha_fin": MIERCOLES + timedelta(days=1)})
    assert accion.titulo == "Llamar — Tornillos del Bajío"
    assert acciones_prospeccion([futura, accion], MIERCOLES) == [accion.id]

    plan = componer_plan(["p1", "p2"], ["ayer"], ["s1", "p1", "s2", "s3", "s4"])
    assert plan == ["p1", "p2", "ayer", "s1", "s2", "s3"]
    muchas = [f"p{i}" for i in range(8)]
    assert componer_plan(muchas, ["ayer"], []) == muchas[:6]          # pueden llenar el día
    assert componer_plan(muchas, ["ayer"], [], tope_prospeccion=4)[4] == "ayer"


def test_sin_tarea_si_el_prospecto_esta_cerrado_o_sin_fecha():
    assert tarea_de_accion(prospecto(), None, "x") is None
    cerrado = prospecto(etapa="ganado", fecha_proxima_accion=MIERCOLES)
    assert tarea_de_accion(cerrado, None, "x") is None


# ---------- API ----------

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEX_TOKEN", "token-alex")
    repo = Repositorio(ruta=tmp_path / "d.json")
    aplicar_fase0(repo, hoy_local())
    cliente = TestClient(crear_app(repo))
    cliente.repo = repo
    return cliente


def test_flujo_de_captacion_por_api(api):
    hoy = hoy_local()
    p = api.post("/api/captacion/prospectos", json={
        "empresa": "Plásticos QRO", "segmento": "independiente", "origen": "canacintra",
        "proxima_accion": "Llamar", "fecha_proxima_accion": hoy.isoformat(),
    }).json()
    assert (p["monto_desarrollo"], p["monto_mensual"]) == (3000, 3500)
    assert p["fechas_etapa"] == {"identificado": hoy.isoformat()}

    # Su próxima acción es tarea real y encabeza el plan de hoy
    plan = api.get("/api/hoy").json()["tareas"]
    assert plan[0]["prospecto_id"] == p["id"] and plan[0]["titulo"] == "Llamar — Plásticos QRO"

    # Registrar interacción: cierra la acción, pasa a contactado y agenda la siguiente
    r = api.post(f"/api/captacion/prospectos/{p['id']}/interacciones", json={
        "canal": "whatsapp", "resultado": "Interesado",
        "proxima_accion": "Enviar demo", "fecha_proxima_accion": (hoy + timedelta(days=3)).isoformat(),
    }).json()
    assert r["prospecto"]["etapa"] == "contactado"
    tareas = [t for t in api.repo.tareas.values() if t.prospecto_id == p["id"]]
    assert sorted(t.estado for t in tareas) == ["hecha", "pendiente"]

    # Perdido sin motivo → 422; con motivo, la tarea abierta desaparece
    assert api.patch(f"/api/captacion/prospectos/{p['id']}", json={"etapa": "perdido"}).status_code == 422
    ok = api.patch(f"/api/captacion/prospectos/{p['id']}", json={"etapa": "perdido", "motivo_perdida": "Sin presupuesto"})
    assert ok.status_code == 200
    assert api.repo.accion_pendiente(p["id"]) is None

    tablero = api.get("/api/captacion").json()
    assert tablero["kpis"]["interacciones_semana"] == 1
    assert tablero["kpis"]["por_etapa"]["perdido"] == 1


def test_ganar_actualiza_el_objetivo_smart_calculado(api):
    p = api.post("/api/captacion/prospectos", json={"empresa": "Metalmecánica Norte"}).json()
    api.patch(f"/api/captacion/prospectos/{p['id']}", json={"etapa": "ganado"})
    sin = api.repo.proyecto_captacion()
    objetivo = next(o for o in api.repo.objetivos_de(sin.id) if o.metrica == "clientes pagando")
    assert objetivo.valor_actual == 1
    assert api.get("/api/captacion").json()["kpis"]["mrr_actual"] == 4000


def test_salud_de_sinprotek_se_pone_roja_con_4_prospectos_sin_contacto(api):
    for i in range(4):
        p = Prospecto(empresa=f"Viejo {i}", creado=datetime(2026, 1, 1))
        api.repo.prospectos[p.id] = p
    portafolio = api.get("/api/portafolio").json()["proyectos"]
    sin = next(x for x in portafolio if x["nombre"].startswith("SINPROTEK"))
    assert sin["kpis"]["salud"] == "rojo"


def test_config_meta_semanal(api):
    assert api.put("/api/captacion/config", json={"meta_interacciones_semana": 30}).status_code == 200
    assert api.get("/api/captacion").json()["kpis"]["meta_semana"] == 30
    assert api.put("/api/captacion/config", json={"tope_prospeccion_ivy": 9}).status_code == 422


# ---------- Alex (VAPI) ----------

def test_alex_exige_su_propio_token(api):
    assert api.post("/api/captacion/alex", json={"telefono": "4421234567"}).status_code == 401
    malo = {"Authorization": "Bearer otro"}
    assert api.post("/api/captacion/alex", json={}, headers=malo).status_code == 401


def test_alex_formato_vapi_crea_prospecto_y_agenda_reunion(api):
    cuerpo = {"message": {
        "type": "tool-calls",
        "call": {"customer": {"number": "+524421234567"}},
        "toolCallList": [{
            "id": "call_1", "type": "function",
            "function": {"name": "registrar_resultado", "arguments": {
                "empresa": "Lácteos Colón", "contacto": "Marta", "resultado": "Agendó reunión",
                "agendo_cita": True, "fecha_cita": "2026-09-30",
            }},
        }],
    }}
    r = api.post("/api/captacion/alex", json=cuerpo, headers={"Authorization": "Bearer token-alex"})
    assert r.status_code == 200
    resultado = r.json()["results"][0]
    assert resultado["toolCallId"] == "call_1" and "Lácteos Colón" in resultado["result"]

    p = next(x for x in api.repo.prospectos.values() if x.empresa == "Lácteos Colón")
    assert p.origen == "llamada_alex" and p.etapa == "reunion_agendada"
    assert p.fecha_proxima_accion == date(2026, 9, 30)
    assert api.repo.interacciones_de(p.id)[0].canal == "alex"

    # Segunda llamada al mismo número (otro formato): no duplica el prospecto
    plano = {"telefono": "442 123 4567", "resultado": "Pidió cotización", "agendo_cita": False}
    api.post("/api/captacion/alex", json=plano, headers={"Authorization": "Bearer token-alex"})
    assert sum(1 for x in api.repo.prospectos.values() if x.empresa == "Lácteos Colón") == 1
    assert len(api.repo.interacciones_de(p.id)) == 2
