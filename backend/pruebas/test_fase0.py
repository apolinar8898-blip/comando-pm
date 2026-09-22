"""Tests de la Fase 0: rutinas, hora de Querétaro, repositorio Supabase (sin red),
login con APP_PASSWORD y la carga del portafolio real."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.dominio import (
    fechas_a_generar,
    instancia,
    rutina_expirada,
    spi,
    sugerir_plan_dia,
    tareas_vencidas,
)
from app.dominio.rutinas import MAX_DIAS_RELLENO
from app.main import crear_app
from app.modelos import Proyecto, Rutina, Tarea
from app.reloj import hoy_en
from app.repositorio import Repositorio
from app.repositorio_supabase import RepositorioSupabase, a_texto, calcular_cambios
from app.semilla_real import aplicar_fase0

MARTES = date(2026, 9, 22)  # martes


def rutina(**kwargs) -> Rutina:
    base = dict(proyecto_id="p1", titulo="Easy run Z2", dias_semana=[0, 1, 2, 3, 4, 5, 6], desde=MARTES)
    base.update(kwargs)
    return Rutina(**base)


# ---------- Rutinas ----------

def test_rutina_genera_solo_sus_dias_y_nunca_a_futuro():
    r = rutina(dias_semana=[0, 2], desde=date(2026, 9, 14))  # lunes y miércoles
    assert fechas_a_generar(r, MARTES) == [date(2026, 9, 14), date(2026, 9, 16), date(2026, 9, 21)]


def test_rutina_no_repite_lo_ya_generado_y_respeta_hasta_y_activa():
    r = rutina(generada_hasta=MARTES - timedelta(days=1))
    assert fechas_a_generar(r, MARTES) == [MARTES]
    assert fechas_a_generar(rutina(generada_hasta=MARTES), MARTES) == []
    assert fechas_a_generar(rutina(desde=MARTES - timedelta(days=5), hasta=MARTES - timedelta(days=4)), MARTES) == [
        MARTES - timedelta(days=5), MARTES - timedelta(days=4)]
    assert fechas_a_generar(rutina(activa=False), MARTES) == []


def test_rutina_rellena_como_maximo_un_mes_hacia_atras():
    r = rutina(desde=date(2026, 1, 1))
    fechas = fechas_a_generar(r, MARTES)
    assert len(fechas) == MAX_DIAS_RELLENO
    assert fechas[-1] == MARTES


def test_rutina_invalida_se_rechaza():
    with pytest.raises(ValueError):
        rutina(dias_semana=[7])
    with pytest.raises(ValueError):
        rutina(dias_semana=[])
    with pytest.raises(ValueError):
        rutina(hasta=MARTES - timedelta(days=1))


def test_rutina_expirada_no_es_vencida_ni_se_sugiere_pero_pesa_en_spi():
    r = rutina()
    ayer = instancia(r, MARTES - timedelta(days=1))
    hoy_ = instancia(r, MARTES)
    assert rutina_expirada(ayer, MARTES) and not rutina_expirada(hoy_, MARTES)
    assert tareas_vencidas([ayer, hoy_], MARTES) == []
    assert sugerir_plan_dia([ayer, hoy_], MARTES) == [hoy_.id]
    assert spi([ayer], MARTES) == pytest.approx(0.0)  # no se hizo: la adherencia cae
    hecha = ayer.model_copy(update={"estado": "hecha"})
    assert not rutina_expirada(hecha, MARTES)
    assert spi([hecha], MARTES) == pytest.approx(1.0)


def test_tarea_normal_vencida_sigue_siendo_vencida():
    normal = Tarea(proyecto_id="p1", titulo="x", fecha_inicio=MARTES - timedelta(days=3),
                   fecha_fin=MARTES - timedelta(days=1))
    assert tareas_vencidas([normal], MARTES) == [normal]


# ---------- Hora de Querétaro ----------

def test_hoy_es_el_de_queretaro_no_el_de_utc():
    # 23/09 01:00 UTC = 22/09 19:00 en Querétaro (UTC−6)
    instante = datetime(2026, 9, 23, 1, 0, tzinfo=timezone.utc)
    assert hoy_en(instante, ZoneInfo("America/Mexico_City")) == date(2026, 9, 22)
    assert hoy_en(datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc), ZoneInfo("America/Mexico_City")) == date(2026, 9, 23)


# ---------- Repositorio Supabase (sin red) ----------

def test_diff_detecta_altas_cambios_y_bajas():
    antes = {"tareas": {("a",): {"id": "a", "titulo": "uno"}, ("b",): {"id": "b", "titulo": "dos"}}}
    despues = {"tareas": {("a",): {"id": "a", "titulo": "uno"}, ("b",): {"id": "b", "titulo": "DOS"},
                          ("c",): {"id": "c", "titulo": "tres"}}}
    cambios = calcular_cambios(antes, despues)
    assert [f["id"] for f in cambios["tareas"]["upserts"]] == ["b", "c"]
    assert cambios["tareas"]["deletes"] == []
    assert calcular_cambios(despues, antes)["tareas"]["deletes"] == [("c",)]
    assert calcular_cambios(antes, antes) == {}


def test_valores_a_texto_para_postgres():
    assert a_texto(["a", "b"], "uuid[]") == "{a,b}"
    assert a_texto([], "uuid[]") == "{}"
    assert a_texto({"x": "ñ"}, "jsonb") == '{"x": "ñ"}'
    assert a_texto(True, "boolean") == "true"
    assert a_texto(None, "date") is None
    assert a_texto(3.5, "numeric") == "3.5"


class ConexionFalsa:
    """Imita lo mínimo de psycopg: registra el SQL, DB vacía al cargar."""

    def __init__(self, bitacora: list):
        self.bitacora = bitacora

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self, row_factory=None):
        conexion = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                conexion.bitacora.append(sql)

            def fetchall(self):
                return []

        return Cursor()

    def transaction(self):
        return self

    def execute(self, sql, params=None):
        self.bitacora.append(sql)


def test_supabase_guarda_solo_lo_que_cambio_y_borra_antes_de_insertar():
    bitacora: list[str] = []
    repo = RepositorioSupabase("falso", conectar=lambda: ConexionFalsa(bitacora))
    assert repo.vacio()

    p = Proyecto(nombre="SINPROTEK", fecha_inicio=MARTES, fecha_fin_objetivo=date(2026, 12, 31))
    t = Tarea(proyecto_id=p.id, titulo="Llamar", fecha_inicio=MARTES, fecha_fin=MARTES)
    repo.proyectos[p.id] = p
    repo.tareas[t.id] = t
    bitacora.clear()
    repo.guardar()
    inserts = [s for s in bitacora if s.startswith("insert")]
    assert len(inserts) == 2 and "into proyectos" in inserts[0] and "into tareas" in inserts[1]

    bitacora.clear()
    repo.guardar()  # sin cambios → sin conexión
    assert bitacora == []

    del repo.tareas[t.id]
    repo.proyectos[p.id].nombre = "SINPROTEK – Captación"
    bitacora.clear()
    repo.guardar()
    escrituras = [s for s in bitacora if s.startswith(("insert", "delete"))]
    assert escrituras[0].startswith("delete from tareas")
    assert "into proyectos" in escrituras[1] and len(escrituras) == 2


# ---------- API: seguridad, ping y rutinas ----------

def test_app_password_exige_token_y_ping_es_publico(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "clave larga de prueba")
    api = TestClient(crear_app(Repositorio(ruta=tmp_path / "d.json")))
    assert api.get("/api/portafolio").status_code == 401
    assert api.get("/api/portafolio", headers={"X-Token": "mala"}).status_code == 401
    assert api.get("/api/portafolio", headers={"X-Token": "clave larga de prueba"}).status_code == 200
    assert api.get("/api/ping").status_code == 200


def test_rutina_por_api_aparece_en_el_plan_de_hoy(tmp_path):
    api = TestClient(crear_app(Repositorio(ruta=tmp_path / "d.json")))
    p = api.post("/api/proyectos", json={"nombre": "IRONMAN", "fecha_inicio": "2026-09-01",
                                         "fecha_fin_objetivo": "2026-11-08"}).json()
    r = api.post(f"/api/proyectos/{p['id']}/rutinas",
                 json={"titulo": "Natación", "dias_semana": list(range(7))}).json()
    assert r["desde"]  # por defecto: hoy

    hoy = api.get("/api/hoy").json()
    assert [t["titulo"] for t in hoy["tareas"]] == ["Natación"]
    # Idempotente: volver a pedir no crea otra instancia
    api.get("/api/hoy")
    tareas = api.get(f"/api/tareas?proyecto_id={p['id']}").json()["tareas"]
    assert len(tareas) == 1 and tareas[0]["rutina_id"] == r["id"] and tareas[0]["expirada"] is False

    # Desactivar (nada se borra) y datos inválidos → 422
    assert api.patch(f"/api/rutinas/{r['id']}", json={"activa": False}).json()["activa"] is False
    assert api.post(f"/api/proyectos/{p['id']}/rutinas", json={"titulo": "x", "dias_semana": [9]}).status_code == 422


# ---------- Portafolio real (Fase 0) ----------

def test_fase0_archiva_demos_cancela_zenzontle_y_es_idempotente(tmp_path):
    from app import datos_demo

    repo = Repositorio(ruta=tmp_path / "d.json")
    datos_demo.sembrar(repo)
    z = Proyecto(nombre="Canciones en Guitarra Zenzontle", fecha_inicio=date(2026, 7, 24),
                 fecha_fin_objetivo=date(2027, 7, 24))
    repo.proyectos[z.id] = z

    informe = aplicar_fase0(repo, MARTES)
    assert informe
    estados = {p.nombre: p.estado for p in repo.proyectos.values()}
    assert estados["Lanzamiento campaña CTWA"] == "cerrado"
    assert estados["Implementación CRM"] == "cerrado"
    assert estados["Canciones en Guitarra Zenzontle"] == "cancelado"
    assert {"SINPROTEK – Captación 3 clientes", "REMAX", "IRONMAN 70.3 Campeche", "Apo Villalón"} <= {
        p.nombre for p in repo.proyectos_activos()}

    im = repo.proyecto_por_nombre("IRONMAN 70.3 Campeche")
    assert any(t.es_hito and t.fecha_fin == date(2026, 11, 8) for t in repo.tareas_de(im.id))
    assert sorted(d for r in repo.rutinas.values() if r.proyecto_id == im.id for d in r.dias_semana) == list(range(7))
    sin = repo.proyecto_por_nombre("SINPROTEK – Captación 3 clientes")
    assert repo.objetivos_de(sin.id)[0].valor_objetivo == 3

    conteo = (len(repo.proyectos), len(repo.tareas), len(repo.rutinas), len(repo.objetivos))
    assert aplicar_fase0(repo, MARTES) == []
    assert conteo == (len(repo.proyectos), len(repo.tareas), len(repo.rutinas), len(repo.objetivos))
