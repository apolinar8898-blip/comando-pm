"""Fase 0: del portafolio demo al portafolio real de Apo (22/09/2026).

Idempotente: correrlo dos veces no duplica nada (busca por nombre de
proyecto y por título de rutina/hito/objetivo). Nada se borra: las demos
se cierran y Zenzontle se cancela, todo queda en el historial.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .modelos import Objetivo, Proyecto, Rutina, Tarea
from .repositorio import Repositorio

DEMOS = ["Lanzamiento campaña CTWA", "Implementación CRM"]
ZENZONTLE = "Canciones en Guitarra Zenzontle"
APO = "Apo Villalón"
FIN_2026 = date(2026, 12, 31)
CARRERA = date(2026, 11, 8)

L, M, X, J, V, S, D = range(7)
LUN_A_VIE = [L, M, X, J, V]


def _fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _proyecto(repo: Repositorio, informe: list[str], **datos) -> Proyecto:
    existente = repo.proyecto_por_nombre(datos["nombre"])
    if existente:
        return existente
    proyecto = Proyecto.model_validate(datos)
    repo.proyectos[proyecto.id] = proyecto
    informe.append(f"+ proyecto {proyecto.nombre}")
    return proyecto


def _rutina(repo: Repositorio, informe: list[str], proyecto: Proyecto, hoy: date,
            titulo: str, dias: list[int], horas: float, hasta: Optional[date] = None) -> None:
    if any(r.proyecto_id == proyecto.id and r.titulo == titulo for r in repo.rutinas.values()):
        return
    rutina = Rutina(proyecto_id=proyecto.id, titulo=titulo, dias_semana=dias,
                    esfuerzo_estimado_h=horas, desde=hoy, hasta=hasta)
    repo.rutinas[rutina.id] = rutina
    informe.append(f"  + rutina {titulo}")


def _hito(repo: Repositorio, informe: list[str], proyecto: Proyecto, titulo: str, fecha: date) -> None:
    if any(t.titulo == titulo for t in repo.tareas_de(proyecto.id)):
        return
    tarea = Tarea(proyecto_id=proyecto.id, titulo=titulo, fecha_inicio=fecha, fecha_fin=fecha,
                  es_hito=True, importante=True, esfuerzo_estimado_h=0)
    repo.tareas[tarea.id] = tarea
    informe.append(f"  + hito {titulo} ({_fecha(fecha)})")


def _objetivo(repo: Repositorio, informe: list[str], proyecto: Proyecto, **datos) -> None:
    if any(o.especifico == datos["especifico"] for o in repo.objetivos_de(proyecto.id)):
        return
    objetivo = Objetivo.model_validate({**datos, "proyecto_id": proyecto.id})
    repo.objetivos[objetivo.id] = objetivo
    informe.append(f"  + objetivo SMART {objetivo.especifico}")


def aplicar_fase0(repo: Repositorio, hoy: date) -> list[str]:
    """Aplica la limpieza y los proyectos reales. Devuelve un informe legible."""
    informe: list[str] = []

    # 1. Archivar demos (cerrado + lección) y cancelar Zenzontle.
    for nombre in DEMOS:
        p = repo.proyecto_por_nombre(nombre)
        if p and p.estado == "activo":
            p.estado = "cerrado"
            p.lecciones = (p.lecciones + "\n" if p.lecciones else "") + \
                f"Proyecto demo archivado el {_fecha(hoy)} (Fase 0)."
            informe.append(f"~ archivado (cerrado) {nombre}")
    z = repo.proyecto_por_nombre(ZENZONTLE)
    if z and z.estado == "activo":
        z.estado = "cancelado"
        z.lecciones = (z.lecciones + "\n" if z.lecciones else "") + \
            f"Cancelado por decisión de Apo el {_fecha(hoy)}: foco en SINPROTEK, REMAX e IRONMAN."
        informe.append(f"~ cancelado {ZENZONTLE}")

    # 2. SINPROTEK — la meta que gobierna todo.
    sin = _proyecto(
        repo, informe,
        nombre="SINPROTEK – Captación 3 clientes",
        descripcion="Agentes de IA por WhatsApp y voz (Alex) para PyMEs. Clúster prioritario: CANACINTRA Querétaro.",
        fecha_inicio=hoy, fecha_fin_objetivo=FIN_2026, color="#2a78d6", prioridad=1,
    )
    _objetivo(
        repo, informe, sin,
        especifico="3 clientes pagando SINPROTEK/PropIA antes del 31/12/2026",
        metrica="clientes pagando", valor_objetivo=3, valor_actual=0,
        alcanzable="5 prospectos por día hábil ≈ 300 contactos al 31/12; con 1 % de cierre bastan",
        relevante="Es la meta que gobierna todo: valida el negocio y reemplaza el ingreso de Uber",
        fecha_limite=FIN_2026,
    )
    _hito(repo, informe, sin, "3 clientes pagando", FIN_2026)
    _rutina(repo, informe, sin, hoy, "Prospectar 5 clientes potenciales y agendar cita", LUN_A_VIE, 2)

    # 3. REMAX — 1 captación, 1 venta y 1 renta por mes.
    remax = _proyecto(
        repo, informe,
        nombre="REMAX",
        descripcion="Agente de ventas REMAX Infinity (Jardines de la Hacienda), todo Querétaro.",
        fecha_inicio=hoy, fecha_fin_objetivo=FIN_2026, color="#d03b3b", prioridad=2,
    )
    for metrica, verbo in (("propiedades captadas", "Captar"), ("ventas cerradas", "Vender"),
                           ("rentas cerradas", "Rentar")):
        _objetivo(
            repo, informe, remax,
            especifico=f"{verbo} 1 propiedad por mes (oct–dic 2026)",
            metrica=metrica, valor_objetivo=3, valor_actual=0,
            alcanzable="Ritmo de 1 por mes en todo Querétaro",
            relevante="Comisión: 25 % como captador y 25 % por traer comprador",
            fecha_limite=FIN_2026,
        )
    for mes, cierre in (("octubre", date(2026, 10, 31)), ("noviembre", date(2026, 11, 30)),
                        ("diciembre", FIN_2026)):
        for verbo in ("Captar", "Vender", "Rentar"):
            _hito(repo, informe, remax, f"{verbo} 1 propiedad — {mes}", cierre)

    # 4. IRONMAN 70.3 Campeche — plan semanal de Apo.
    im = _proyecto(
        repo, informe,
        nombre="IRONMAN 70.3 Campeche",
        descripcion="Carrera 08/11/2026. Registro con Galaxy Watch5 Pro + Polar H10 → Strava. Peso objetivo: 86 kg.",
        fecha_inicio=hoy, fecha_fin_objetivo=CARRERA, color="#f08c00", prioridad=2,
    )
    _objetivo(
        repo, informe, im,
        especifico="Terminar el IRONMAN 70.3 Campeche el 08/11/2026",
        metrica="carreras terminadas", valor_objetivo=1, valor_actual=0,
        alcanzable="Plan semanal de 7 días con zona 2, método noruego y fondos largos",
        relevante="Disciplina y salud que sostienen todo lo demás",
        fecha_limite=CARRERA,
    )
    _hito(repo, informe, im, "Día de carrera — IRONMAN 70.3 Campeche", CARRERA)
    vispera = date(2026, 11, 7)
    for titulo, dia, horas in (
        ("Easy run Z2 + natación", L, 1.5),
        ("Easy bike Z2 + natación", M, 1.5),
        ("Carrera método noruego + fuerza", X, 1.5),
        ("Bici método noruego", J, 1.25),
        ("Carrera distancia larga", V, 1.5),
        ("Bici distancia larga", S, 3),
        ("Natación + fuerza (gym)", D, 1.5),
    ):
        _rutina(repo, informe, im, hoy, titulo, [dia], horas, hasta=vispera)

    # 5. Apo Villalón — marca personal que alimenta la meta de SINPROTEK.
    apo = repo.proyecto_por_nombre(APO)
    if apo is None:
        apo = _proyecto(repo, informe, nombre=APO, fecha_inicio=hoy,
                        fecha_fin_objetivo=date(2027, 12, 24), prioridad=3)
    if not apo.descripcion:
        apo.descripcion = "Marca personal en LinkedIn/YouTube: contenido que alimenta la meta de SINPROTEK."
    _rutina(repo, informe, apo, hoy, "LinkedIn: crear carrusel y publicar post del día", LUN_A_VIE, 1)
    _rutina(repo, informe, apo, hoy, "LinkedIn: comentar y ampliar red", LUN_A_VIE, 0.5)
    _rutina(repo, informe, apo, hoy, "Grabar video largo de la semana", [S], 2)
    _rutina(repo, informe, apo, hoy, "Segmentar el video en shorts para redes", [D], 1)

    return informe
