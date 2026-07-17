"""Tests del dominio: cada regla del CLAUDE.md §3 tiene aquí su candado."""
from datetime import date, timedelta

import pytest

from app.dominio import (
    MAX_TAREAS_DIA,
    avance,
    cuadrante_eisenhower,
    es_urgente,
    proximo_hito,
    ruta_critica,
    salud_proyecto,
    spi,
    sugerir_plan_dia,
    tareas_vencidas,
    validar_plan,
)
from app.modelos import Reto, Tarea

HOY = date(2026, 7, 17)


def tarea(**kwargs) -> Tarea:
    base = dict(
        proyecto_id="p1",
        titulo="tarea",
        fecha_inicio=HOY,
        fecha_fin=HOY + timedelta(days=5),
    )
    base.update(kwargs)
    return Tarea(**base)


# ---------- Eisenhower ----------

def test_urgencia_automatica_por_fecha():
    assert es_urgente(tarea(fecha_fin=HOY + timedelta(days=2)), HOY)
    assert not es_urgente(tarea(fecha_fin=HOY + timedelta(days=3)), HOY)


def test_urgencia_manual_gana_a_la_automatica():
    lejana_pero_urgente = tarea(fecha_fin=HOY + timedelta(days=30), urgente_manual=True)
    cercana_pero_no = tarea(fecha_fin=HOY, urgente_manual=False)
    assert es_urgente(lejana_pero_urgente, HOY)
    assert not es_urgente(cercana_pero_no, HOY)


def test_cuadrantes():
    assert cuadrante_eisenhower(tarea(importante=True, fecha_fin=HOY), HOY) == 1
    assert cuadrante_eisenhower(tarea(importante=True, fecha_fin=HOY + timedelta(days=10)), HOY) == 2
    assert cuadrante_eisenhower(tarea(fecha_fin=HOY), HOY) == 3
    assert cuadrante_eisenhower(tarea(fecha_fin=HOY + timedelta(days=10)), HOY) == 4


# ---------- Avance y SPI ----------

def test_avance_ponderado_por_esfuerzo():
    tareas = [
        tarea(estado="hecha", esfuerzo_estimado_h=8),
        tarea(estado="pendiente", esfuerzo_estimado_h=2),
    ]
    assert avance(tareas) == pytest.approx(0.8)
    assert avance([]) == 0.0


def test_spi_en_plan_y_atrasado():
    # Tarea que ya debió terminar y está hecha → SPI 1.0
    terminada = tarea(
        estado="hecha",
        fecha_inicio=HOY - timedelta(days=10),
        fecha_fin=HOY - timedelta(days=5),
        esfuerzo_estimado_h=10,
    )
    assert spi([terminada], HOY) == pytest.approx(1.0)

    # La misma tarea sin hacer → SPI 0.0 (todo lo planificado, nada ganado)
    atrasada = terminada.model_copy(update={"estado": "pendiente"})
    assert spi([atrasada], HOY) == pytest.approx(0.0)

    # Proyecto que aún no arranca → 1.0 (en plan)
    futura = tarea(fecha_inicio=HOY + timedelta(days=5), fecha_fin=HOY + timedelta(days=9))
    assert spi([futura], HOY) == pytest.approx(1.0)

    # El día 1 de una tarea nadie está atrasado → 1.0
    arranca_hoy = tarea(fecha_inicio=HOY, fecha_fin=HOY + timedelta(days=9))
    assert spi([arranca_hoy], HOY) == pytest.approx(1.0)

    # Una tarea en curso gana el 50% de su esfuerzo
    en_curso = tarea(
        estado="en_curso",
        fecha_inicio=HOY - timedelta(days=10),
        fecha_fin=HOY - timedelta(days=1),
        esfuerzo_estimado_h=10,
    )
    assert spi([en_curso], HOY) == pytest.approx(0.5)


# ---------- Salud ----------

def reto(impacto: int, probabilidad: int, estado: str = "abierto") -> Reto:
    return Reto(proyecto_id="p1", titulo="r", impacto=impacto, probabilidad=probabilidad, estado=estado)


def sano() -> list[Tarea]:
    """Proyecto al día: tarea futura sin vencer."""
    return [tarea(fecha_fin=HOY + timedelta(days=10))]


def test_salud_verde_por_defecto():
    assert salud_proyecto(sano(), [], HOY) == "verde"


def test_salud_roja_por_hito_vencido():
    hito = tarea(es_hito=True, fecha_inicio=HOY - timedelta(days=1), fecha_fin=HOY - timedelta(days=1))
    assert salud_proyecto(sano() + [hito], [], HOY) == "rojo"


def test_salud_roja_por_riesgo_critico():
    assert salud_proyecto(sano(), [reto(4, 4)], HOY) == "rojo"


def test_salud_amarilla_por_tarea_vencida():
    # Proyecto mayormente al día (mucho trabajo hecho) con UNA tarea chica vencida:
    # el SPI apenas se mueve, así que se aísla la regla de vencidas → amarillo.
    hecha = tarea(estado="hecha", fecha_inicio=HOY - timedelta(days=10),
                  fecha_fin=HOY - timedelta(days=2), esfuerzo_estimado_h=20)
    vencida = tarea(fecha_inicio=HOY - timedelta(days=3), fecha_fin=HOY - timedelta(days=1),
                    esfuerzo_estimado_h=0.5)
    tareas = sano() + [hecha, vencida]
    assert salud_proyecto(tareas, [], HOY) == "amarillo"
    assert vencida in tareas_vencidas(tareas, HOY)


def test_salud_amarilla_por_riesgo_medio():
    assert salud_proyecto(sano(), [reto(3, 3)], HOY) == "amarillo"


def test_riesgo_cerrado_no_afecta_salud():
    assert salud_proyecto(sano(), [reto(5, 5, estado="cerrado")], HOY) == "verde"


# ---------- Hitos ----------

def test_proximo_hito_es_el_mas_cercano_pendiente():
    h1 = tarea(es_hito=True, titulo="lejano", fecha_inicio=HOY + timedelta(days=30), fecha_fin=HOY + timedelta(days=30))
    h2 = tarea(es_hito=True, titulo="cercano", fecha_inicio=HOY + timedelta(days=3), fecha_fin=HOY + timedelta(days=3))
    hecho = tarea(es_hito=True, estado="hecha", fecha_inicio=HOY, fecha_fin=HOY)
    assert proximo_hito([h1, h2, hecho], HOY).titulo == "cercano"
    assert proximo_hito([hecho], HOY) is None


# ---------- Ivy Lee ----------

def test_sugerencia_prioriza_hitos_luego_q1_luego_q2():
    hito = tarea(titulo="hito", es_hito=True, fecha_inicio=HOY + timedelta(days=5), fecha_fin=HOY + timedelta(days=5))
    q1 = tarea(titulo="q1", importante=True, fecha_fin=HOY + timedelta(days=1))
    q2 = tarea(titulo="q2", importante=True, fecha_fin=HOY + timedelta(days=20))
    q4 = tarea(titulo="q4", fecha_fin=HOY + timedelta(days=20))
    bloqueada = tarea(titulo="bloq", importante=True, estado="bloqueada", fecha_fin=HOY)

    plan = sugerir_plan_dia([q4, q2, q1, hito, bloqueada], HOY)
    assert plan == [hito.id, q1.id, q2.id]  # q4 y bloqueada fuera


def test_sugerencia_respeta_maximo_seis():
    muchas = [tarea(titulo=f"t{i}", importante=True, fecha_fin=HOY) for i in range(10)]
    assert len(sugerir_plan_dia(muchas, HOY)) == MAX_TAREAS_DIA


def test_validar_plan_rechaza_la_septima_y_quita_duplicados():
    assert validar_plan(["a", "a", "b"]) == ["a", "b"]
    with pytest.raises(ValueError):
        validar_plan([str(i) for i in range(7)])


# ---------- Ruta crítica ----------

def test_ruta_critica_elige_la_cadena_mas_larga():
    a = tarea(titulo="a", fecha_inicio=HOY, fecha_fin=HOY + timedelta(days=9))            # 10 días
    b = tarea(titulo="b", fecha_inicio=HOY, fecha_fin=HOY + timedelta(days=1))            # 2 días
    c = tarea(titulo="c", fecha_inicio=HOY, fecha_fin=HOY + timedelta(days=4), dependencias=[a.id])  # a→c = 15
    d = tarea(titulo="d", fecha_inicio=HOY, fecha_fin=HOY + timedelta(days=2), dependencias=[b.id])  # b→d = 5

    criticas = ruta_critica([a, b, c, d])
    assert criticas == {a.id, c.id}


def test_ruta_critica_tolera_dependencias_rotas_y_vacio():
    suelta = tarea(dependencias=["no-existe"])
    assert ruta_critica([suelta]) == {suelta.id}
    assert ruta_critica([]) == set()
