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


def test_documentos_versionado_y_siembra_del_charter(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")
    pid = api.get("/api/portafolio").json()["proyectos"][0]["id"]

    # Crear charter con hitos de alto nivel
    charter = api.post("/api/documentos", json={
        "proyecto_id": pid,
        "tipo": "charter",
        "contenido": {
            "justificacion": "Validar el canal de anuncios",
            "hitos_alto_nivel": [
                {"titulo": "HITO: campaña al aire", "fecha": "2026-08-01"},  # ya existe
                {"titulo": "HITO: primer cliente pagado", "fecha": "2026-08-15"},
            ],
        },
    }).json()
    assert charter["version"] == 1

    # Guardar de nuevo = versión 2 con historial
    v2 = api.put(f"/api/documentos/{charter['id']}", json={
        "contenido": {**charter["contenido"], "justificacion": "Editada"},
    }).json()
    assert v2["version"] == 2
    assert v2["historial"][0]["version"] == 1
    assert v2["historial"][0]["contenido"]["justificacion"] == "Validar el canal de anuncios"

    # Sembrar: crea solo los hitos que no existen (idempotente por título)
    antes = len(api.get(f"/api/tareas?proyecto_id={pid}").json()["tareas"])
    r = api.post(f"/api/documentos/{charter['id']}/sembrar").json()
    assert r["hitos_creados"] == 1 and r["hitos_existentes"] == 1
    despues = api.get(f"/api/tareas?proyecto_id={pid}").json()["tareas"]
    assert len(despues) == antes + 1
    nuevo = next(t for t in despues if t["titulo"] == "HITO: primer cliente pagado")
    assert nuevo["es_hito"] and nuevo["esfuerzo_estimado_h"] == 0
    # Sembrar otra vez no duplica
    assert api.post(f"/api/documentos/{charter['id']}/sembrar").json()["hitos_creados"] == 0

    # Solo charters de proyecto siembran
    canvas = api.post("/api/documentos", json={"proyecto_id": pid, "tipo": "canvas"}).json()
    assert api.post(f"/api/documentos/{canvas['id']}/sembrar").status_code == 400

    # Filtro por proyecto
    docs = api.get(f"/api/documentos?proyecto_id={pid}").json()["documentos"]
    assert {d["tipo"] for d in docs} == {"charter", "canvas"}


def test_objetivos_smart_validacion_dura(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")
    pid = api.get("/api/portafolio").json()["proyectos"][0]["id"]

    # Sin métrica no se guarda (CLAUDE.md §5.3)
    invalido = api.post(f"/api/proyectos/{pid}/objetivos", json={
        "especifico": "Vender más", "metrica": "  ", "valor_objetivo": 10,
        "alcanzable": "sí", "relevante": "sí", "fecha_limite": "2026-09-01",
    })
    assert invalido.status_code == 422
    assert "metrica" in invalido.json()["detail"]

    # Valor objetivo debe ser positivo
    assert api.post(f"/api/proyectos/{pid}/objetivos", json={
        "especifico": "x", "metrica": "ventas", "valor_objetivo": 0,
        "alcanzable": "sí", "relevante": "sí", "fecha_limite": "2026-09-01",
    }).status_code == 422

    # Válido: se crea y el progreso se actualiza con PATCH
    ok = api.post(f"/api/proyectos/{pid}/objetivos", json={
        "especifico": "Cerrar 20 ventas del nuevo canal",
        "metrica": "ventas cerradas", "valor_objetivo": 20,
        "alcanzable": "el embudo ya convierte", "relevante": "ingreso directo",
        "fecha_limite": "2026-09-01",
    }).json()
    actualizado = api.patch(f"/api/objetivos/{ok['id']}", json={"valor_actual": 5}).json()
    assert actualizado["valor_actual"] == 5
    detalle = api.get(f"/api/proyectos/{pid}").json()
    assert any(o["id"] == ok["id"] for o in detalle["objetivos"])

    # Borrar
    assert api.delete(f"/api/objetivos/{ok['id']}").json()["ok"]


def test_rca_siembra_acciones_como_tareas(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")
    pid = api.get("/api/portafolio").json()["proyectos"][0]["id"]

    rca = api.post("/api/documentos", json={
        "proyecto_id": pid,
        "tipo": "rca",
        "contenido": {
            "que_paso": "La campaña se pausó 2 días por saldo insuficiente",
            "causa_raiz": "No hay alerta de saldo bajo en la cuenta publicitaria",
            "acciones": [
                {"titulo": "Configurar alerta de saldo en Meta", "fecha": "2026-07-25"},
                {"titulo": "Domiciliar la recarga mensual", "fecha": "2026-07-30"},
                {"titulo": "  ", "fecha": "2026-08-01"},  # sin título → se ignora
            ],
            "verificacion": {"senal": "30 días sin pausas por saldo", "fecha": "2026-08-20"},
        },
    }).json()

    # Siembra: 2 acciones + 1 verificación = 3 tareas con origen_rca
    r = api.post(f"/api/documentos/{rca['id']}/sembrar-acciones").json()
    assert r["tareas_creadas"] == 3
    tareas = api.get(f"/api/tareas?proyecto_id={pid}").json()["tareas"]
    del_rca = [t for t in tareas if t.get("origen_rca") == rca["id"]]
    assert len(del_rca) == 3
    assert all(t["importante"] for t in del_rca)
    assert any(t["titulo"].startswith("Verificar:") for t in del_rca)

    # Idempotente: repetir no duplica
    r2 = api.post(f"/api/documentos/{rca['id']}/sembrar-acciones").json()
    assert r2["tareas_creadas"] == 0 and r2["ya_existian"] == 3

    # Un RCA sin acciones ni verificación no siembra nada
    vacio = api.post("/api/documentos", json={"proyecto_id": pid, "tipo": "rca"}).json()
    assert api.post(f"/api/documentos/{vacio['id']}/sembrar-acciones").status_code == 400
    # Y un documento que no es RCA tampoco
    canvas = api.post("/api/documentos", json={"proyecto_id": pid, "tipo": "canvas"}).json()
    assert api.post(f"/api/documentos/{canvas['id']}/sembrar-acciones").status_code == 400


def test_cierre_de_proyecto_con_lecciones(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")
    pid = api.get("/api/portafolio").json()["proyectos"][0]["id"]

    cerrado = api.patch(f"/api/proyectos/{pid}", json={
        "estado": "cerrado",
        "lecciones": "Arrancar los creativos una semana antes; el retraso vino de ahí.",
    }).json()
    assert cerrado["estado"] == "cerrado"

    # Archivado, no borrado: sigue consultable y fuera de los activos
    assert api.get(f"/api/proyectos/{pid}").status_code == 200
    todas = api.get("/api/tareas").json()["tareas"]  # solo proyectos activos
    assert all(t["proyecto_id"] != pid for t in todas)


def test_rca_siembra_acciones_como_tareas(tmp_path):
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")
    pid = api.get("/api/portafolio").json()["proyectos"][0]["id"]

    rca = api.post("/api/documentos", json={
        "proyecto_id": pid,
        "tipo": "rca",
        "contenido": {
            "que_paso": "La campaña estuvo pausada 3 días sin que nadie lo notara",
            "porques": [{"texto": "Nadie revisó el panel de Meta", "hijos": [
                {"texto": "No hay responsable de monitoreo diario", "hijos": []},
            ]}],
            "causa_raiz": "No hay responsable de monitoreo diario",
            "acciones": [
                {"titulo": "Configurar alerta de campaña pausada", "fecha": "2026-07-25"},
                {"titulo": "Checklist diario de revisión de campañas", "fecha": "2026-07-22"},
                {"titulo": "Sin fecha, no se siembra"},
            ],
            "verificacion": {"senal": "30 días sin pausas no detectadas", "fecha": "2026-08-20"},
        },
    }).json()

    # Sembrar: 2 acciones con fecha + 1 verificación = 3 tareas con origen_rca
    r = api.post(f"/api/documentos/{rca['id']}/sembrar-acciones").json()
    assert r["tareas_creadas"] == 3
    tareas = api.get(f"/api/tareas?proyecto_id={pid}").json()["tareas"]
    del_rca = [t for t in tareas if t.get("origen_rca") == rca["id"]]
    assert len(del_rca) == 3
    assert any(t["titulo"].startswith("Verificar:") for t in del_rca)
    assert all(t["importante"] for t in del_rca)

    # Idempotente: repetir no duplica
    r2 = api.post(f"/api/documentos/{rca['id']}/sembrar-acciones").json()
    assert r2["tareas_creadas"] == 0 and r2["ya_existian"] == 3

    # Un RCA sin acciones ni verificación no puede sembrar
    vacio = api.post("/api/documentos", json={"proyecto_id": pid, "tipo": "rca"}).json()
    assert api.post(f"/api/documentos/{vacio['id']}/sembrar-acciones").status_code == 400


def test_persistencia_en_archivo(tmp_path):
    ruta = tmp_path / "datos.json"
    api = cliente(tmp_path)
    api.post("/api/demo/sembrar")

    # Un repositorio nuevo sobre el mismo archivo ve los mismos datos
    repo2 = Repositorio(ruta=ruta)
    assert len(repo2.proyectos) == 2
    assert len(repo2.tareas) == 11
