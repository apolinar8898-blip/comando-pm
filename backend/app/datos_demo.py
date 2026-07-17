"""Datos de demostración: dos proyectos realistas para validar el hito de Fase 1.

Las fechas son relativas a hoy para que el Gantt, los semáforos y el plan
del día siempre muestren un escenario vivo.
"""
from __future__ import annotations

from datetime import date, timedelta

from .modelos import Objetivo, Proyecto, Reto, Tarea
from .repositorio import Repositorio


def sembrar(repo: Repositorio, hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    d = lambda n: hoy + timedelta(days=n)  # noqa: E731

    # ---------- Proyecto 1: lanzamiento de campaña ----------
    p1 = Proyecto(
        nombre="Lanzamiento campaña CTWA",
        descripcion="Anuncios click-to-WhatsApp para el negocio de canciones",
        fecha_inicio=d(-20), fecha_fin_objetivo=d(25),
        color="#4f46e5", prioridad=1, fase="Construcción",
        fase_inicio=d(-20), fase_fin=d(10),
    )
    t1 = Tarea(proyecto_id=p1.id, titulo="Definir públicos y presupuesto", estado="hecha",
               fecha_inicio=d(-20), fecha_fin=d(-15), importante=True, esfuerzo_estimado_h=6)
    t2 = Tarea(proyecto_id=p1.id, titulo="Producir 3 creativos de video", estado="hecha",
               fecha_inicio=d(-14), fecha_fin=d(-6), importante=True,
               dependencias=[t1.id], esfuerzo_estimado_h=16)
    t3 = Tarea(proyecto_id=p1.id, titulo="Configurar campaña en Meta", estado="en_curso",
               fecha_inicio=d(-5), fecha_fin=d(1), importante=True,
               dependencias=[t2.id], esfuerzo_estimado_h=8)
    h1 = Tarea(proyecto_id=p1.id, titulo="HITO: campaña al aire", es_hito=True,
               fecha_inicio=d(2), fecha_fin=d(2), importante=True,
               dependencias=[t3.id], esfuerzo_estimado_h=0)
    t4 = Tarea(proyecto_id=p1.id, titulo="Optimizar pujas primera semana",
               fecha_inicio=d(3), fecha_fin=d(9), importante=True,
               dependencias=[h1.id], esfuerzo_estimado_h=10)
    t5 = Tarea(proyecto_id=p1.id, titulo="Reporte de resultados y decisión de escala",
               fecha_inicio=d(10), fecha_fin=d(14), importante=True,
               dependencias=[t4.id], esfuerzo_estimado_h=6)
    r1 = Reto(proyecto_id=p1.id, titulo="Meta puede rechazar los creativos",
              tipo="riesgo", impacto=4, probabilidad=3,
              plan_de_respuesta="Tener 2 creativos alternos aprobables; revisar políticas antes de subir")
    o1 = Objetivo(proyecto_id=p1.id,
                  especifico="Conseguir conversaciones de WhatsApp calificadas con la campaña",
                  metrica="conversaciones iniciadas/semana", valor_objetivo=50, valor_actual=0,
                  alcanzable="Con $150/día y CTR promedio del nicho alcanza",
                  relevante="Las conversaciones son la entrada del embudo de ventas",
                  fecha_limite=d(25))

    # ---------- Proyecto 2: implementación de CRM ----------
    p2 = Proyecto(
        nombre="Implementación CRM",
        descripcion="Migrar clientes y pipeline a un CRM ordenado",
        fecha_inicio=d(-30), fecha_fin_objetivo=d(15),
        color="#0e9f6e", prioridad=2, fase="Migración",
        fase_inicio=d(-10), fase_fin=d(15),
    )
    u1 = Tarea(proyecto_id=p2.id, titulo="Elegir CRM y plan", estado="hecha",
               fecha_inicio=d(-30), fecha_fin=d(-25), importante=True, esfuerzo_estimado_h=5)
    u2 = Tarea(proyecto_id=p2.id, titulo="Limpiar base de clientes", estado="hecha",
               fecha_inicio=d(-24), fecha_fin=d(-12), importante=True,
               dependencias=[u1.id], esfuerzo_estimado_h=20)
    u3 = Tarea(proyecto_id=p2.id, titulo="Importar contactos y pipeline", estado="pendiente",
               fecha_inicio=d(-8), fecha_fin=d(-2), importante=True,
               dependencias=[u2.id], esfuerzo_estimado_h=12)  # vencida → amarillo/rojo
    h2 = Tarea(proyecto_id=p2.id, titulo="HITO: CRM operando al 100%", es_hito=True,
               fecha_inicio=d(12), fecha_fin=d(12), importante=True,
               dependencias=[u3.id], esfuerzo_estimado_h=0)
    u4 = Tarea(proyecto_id=p2.id, titulo="Capacitarme en flujos de seguimiento",
               fecha_inicio=d(1), fecha_fin=d(8), importante=True,
               dependencias=[u3.id], esfuerzo_estimado_h=8)
    r2 = Reto(proyecto_id=p2.id, titulo="Datos duplicados pueden ensuciar el pipeline",
              tipo="riesgo", impacto=3, probabilidad=3,
              plan_de_respuesta="Regla de deduplicación por teléfono antes de importar")
    r3 = Reto(proyecto_id=p2.id, titulo="Decidir si se migra el histórico 2024",
              tipo="decision_pendiente", impacto=2, probabilidad=2,
              plan_de_respuesta="Evaluar costo/beneficio esta semana")
    o2 = Objetivo(proyecto_id=p2.id,
                  especifico="Tener el 100% de clientes activos gestionados en el CRM",
                  metrica="% clientes en CRM", valor_objetivo=100, valor_actual=60,
                  alcanzable="La base ya está limpia; solo falta importar",
                  relevante="Sin CRM se pierden seguimientos y ventas",
                  fecha_limite=d(15))

    for p in (p1, p2):
        repo.proyectos[p.id] = p
    for t in (t1, t2, t3, h1, t4, t5, u1, u2, u3, h2, u4):
        repo.tareas[t.id] = t
    for r in (r1, r2, r3):
        repo.retos[r.id] = r
    for o in (o1, o2):
        repo.objetivos[o.id] = o
    repo.guardar()
