"""Test de integración de la API: siembra demo y recorre los endpoints clave."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import crear_app
from app.repositorio import Repositorio


def cliente(tmp_path: Path) -> TestClient:
    repo = Repositorio(ruta=tmp_path / "datos.json")
    return TestClient(crear_app(repo))


def test_flujo_completo(tmp_path):
    api = cliente(tmp_path)

    # Sembrar demo (y no dejar que pise datos existentes)
    assert api.post("/api/demo/sembrar").status_code == 200
    assert api.post("/api/demo/sembrar").status_code == 409

    # Portafolio: proyectos con KPIs calculados
    portafolio = api.get("/api/portafolio").json()["proyectos"]
    assert len(portafolio) == 2
    for p in portafolio:
        assert p["kpis"]["salud"] in ("verde", "amarillo", "rojo")
        assert 0 <= p["kpis"]["avance_pct"] <= 100
    # El CRM tiene una tarea vencida sembrada → no puede estar verde
    crm = next(p for p in portafolio if "CRM" in p["nombre"])
    assert crm["kpis"]["salud"] in ("amarillo", "rojo")
    assert crm["kpis"]["tareas_vencidas"] >= 1

    # Detalle: trae tareas expandidas y ruta crítica no vacía
    detalle = api.get(f"/api/proyectos/{crm['id']}").json()
    assert detalle["ruta_critica"]
    assert all("cuadrante" in t for t in detalle["tareas"])

    # Hoy: plan Ivy Lee autogenerado, máximo 6
    hoy = api.get("/api/hoy").json()
    assert 1 <= len(hoy["tareas"]) <= 6
    assert not hoy["cerrado"]

    # El límite de 6 es duro
    ids = [t["id"] for t in hoy["tareas"]] + [t["id"] for t in hoy["candidatas"]]
    if len(ids) >= 7:
        assert api.put("/api/hoy", json={"tarea_ids": ids[:7]}).status_code == 400
    assert api.put("/api/hoy", json={"tarea_ids": ids[:3]}).status_code == 200

    # Completar una tarea del plan y cerrar el día
    primera = hoy["tareas"][0]["id"]
    r = api.patch(f"/api/tareas/{primera}", json={"estado": "hecha"})
    assert r.json()["estado"] == "hecha"
    cierre = api.post("/api/hoy/cerrar", json={"nota": "buen día"}).json()
    assert cierre["ok"]

    # Snapshot diario quedó registrado para la gráfica
    detalle = api.get(f"/api/proyectos/{crm['id']}").json()
    assert len(detalle["snapshots"]) == 1


def test_tareas_expandidas_y_cambio_de_cuadrante(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")

    # Listado global: solo proyectos activos, con cuadrante y datos del proyecto
    todas = api.get("/api/tareas").json()["tareas"]
    assert len(todas) == 11
    assert all({"cuadrante", "proyecto_nombre", "proyecto_color"} <= set(t) for t in todas)

    # Filtro por proyecto
    pid = todas[0]["proyecto_id"]
    del_proyecto = api.get(f"/api/tareas?proyecto_id={pid}").json()["tareas"]
    assert all(t["proyecto_id"] == pid for t in del_proyecto)
    assert api.get("/api/tareas?proyecto_id=no-existe").status_code == 404

    # Mover de cuadrante = fijar flags manuales (drag & drop de la matriz)
    lejana = next(t for t in todas if t["cuadrante"] in (2, 4))
    r = api.patch(
        f"/api/tareas/{lejana['id']}",
        json={"importante": False, "urgente_manual": True},
    ).json()
    assert r["cuadrante"] == 3  # urgente manual, no importante


def test_persistencia_en_archivo(tmp_path):
    ruta = tmp_path / "datos.json"
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")

    # Un repositorio nuevo sobre el mismo archivo ve los mismos datos
    repo2 = Repositorio(ruta=ruta)
    assert len(repo2.proyectos) == 2
    assert len(repo2.tareas) == 11
