"""API de Comando PM (FastAPI).

El frontend no calcula reglas de negocio: todo KPI, semáforo y sugerencia
sale de aquí, que a su vez delega en el paquete dominio/ (lógica pura).
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import datos_demo
from .dominio import (
    avance,
    cuadrante_eisenhower,
    proximo_hito,
    ruta_critica,
    salud_proyecto,
    spi,
    sugerir_plan_dia,
    tareas_vencidas,
    validar_plan,
)
from .modelos import Documento, KpiSnapshot, Objetivo, PlanDia, Proyecto, Reto, Tarea
from .repositorio import Repositorio


# ---------- Seguridad mínima (un solo usuario) ----------

def _verificar_token(x_token: Optional[str] = Header(default=None)) -> None:
    esperado = os.environ.get("APP_PASSWORD")
    if esperado and x_token != esperado:
        raise HTTPException(status_code=401, detail="Token inválido")


# ---------- Cuerpos de petición ----------

class CuerpoPlan(BaseModel):
    tarea_ids: list[str]


class CuerpoCierre(BaseModel):
    nota: str = ""


# ---------- Fábrica de la app (inyectable para tests) ----------

def crear_app(repo: Optional[Repositorio] = None) -> FastAPI:
    repo = repo or Repositorio()
    app = FastAPI(title="Comando PM", dependencies=[Depends(_verificar_token)])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----- Helpers -----

    def _kpis(proyecto: Proyecto, hoy: date) -> dict[str, Any]:
        tareas = repo.tareas_de(proyecto.id)
        retos = repo.retos_de(proyecto.id)
        hito = proximo_hito(tareas, hoy)
        return {
            "salud": salud_proyecto(tareas, retos, hoy),
            "avance_pct": round(avance(tareas) * 100, 1),
            "spi": round(spi(tareas, hoy), 2),
            "tareas_vencidas": len(tareas_vencidas(tareas, hoy)),
            "retos_abiertos": sum(1 for r in retos if r.estado == "abierto"),
            "proximo_hito": (
                {"id": hito.id, "titulo": hito.titulo, "fecha": hito.fecha_fin.isoformat()}
                if hito else None
            ),
            "dias_para_fin": (proyecto.fecha_fin_objetivo - hoy).days,
        }

    def _asegurar_snapshots(hoy: date) -> None:
        """Foto diaria de KPIs por proyecto activo (para gráficas de tendencia)."""
        cambio = False
        for p in repo.proyectos_activos():
            if repo.snapshot_existe(p.id, hoy):
                continue
            k = _kpis(p, hoy)
            repo.snapshots.append(KpiSnapshot(
                proyecto_id=p.id, fecha=hoy,
                avance_pct=k["avance_pct"], spi=k["spi"],
                tareas_vencidas=k["tareas_vencidas"],
                retos_abiertos=k["retos_abiertos"], salud=k["salud"],
            ))
            cambio = True
        if cambio:
            repo.guardar()

    def _tarea_expandida(tarea: Tarea, hoy: date) -> dict[str, Any]:
        proyecto = repo.proyectos.get(tarea.proyecto_id)
        return {
            **tarea.model_dump(mode="json"),
            "cuadrante": cuadrante_eisenhower(tarea, hoy),
            "proyecto_nombre": proyecto.nombre if proyecto else "?",
            "proyecto_color": proyecto.color if proyecto else "#888",
        }

    def _aplicar_cambios(modelo: BaseModel, cambios: dict) -> Any:
        combinado = {**modelo.model_dump(), **cambios}
        return type(modelo).model_validate(combinado)

    def _obtener(coleccion: dict, id_: str, nombre: str) -> Any:
        item = coleccion.get(id_)
        if item is None:
            raise HTTPException(status_code=404, detail=f"{nombre} no encontrado")
        return item

    # ----- Salud del servicio -----

    @app.get("/api/salud")
    def salud_servicio():
        return {"ok": True, "proyectos": len(repo.proyectos)}

    # ----- Portafolio y proyectos -----

    @app.get("/api/portafolio")
    def portafolio():
        hoy = date.today()
        _asegurar_snapshots(hoy)
        return {
            "proyectos": [
                {**p.model_dump(mode="json"), "kpis": _kpis(p, hoy)}
                for p in sorted(
                    repo.proyectos.values(),
                    key=lambda x: (x.estado != "activo", x.prioridad, x.fecha_fin_objetivo),
                )
            ]
        }

    @app.post("/api/proyectos")
    def crear_proyecto(datos: dict):
        proyecto = Proyecto.model_validate(datos)
        repo.proyectos[proyecto.id] = proyecto
        repo.guardar()
        return proyecto.model_dump(mode="json")

    @app.get("/api/proyectos/{pid}")
    def detalle_proyecto(pid: str):
        hoy = date.today()
        proyecto = _obtener(repo.proyectos, pid, "Proyecto")
        tareas = sorted(repo.tareas_de(pid), key=lambda t: (t.fecha_inicio, t.fecha_fin))
        return {
            "proyecto": proyecto.model_dump(mode="json"),
            "kpis": _kpis(proyecto, hoy),
            "tareas": [_tarea_expandida(t, hoy) for t in tareas],
            "ruta_critica": sorted(ruta_critica(tareas)),
            "retos": [r.model_dump(mode="json") for r in repo.retos_de(pid)],
            "objetivos": [o.model_dump(mode="json") for o in repo.objetivos_de(pid)],
            "snapshots": [s.model_dump(mode="json") for s in repo.snapshots_de(pid)],
        }

    @app.patch("/api/proyectos/{pid}")
    def editar_proyecto(pid: str, cambios: dict):
        proyecto = _obtener(repo.proyectos, pid, "Proyecto")
        repo.proyectos[pid] = _aplicar_cambios(proyecto, cambios)
        repo.guardar()
        return repo.proyectos[pid].model_dump(mode="json")

    # ----- Tareas -----

    @app.get("/api/tareas")
    def listar_tareas(proyecto_id: Optional[str] = None):
        """Tareas expandidas (con cuadrante y proyecto) para Eisenhower y plan semanal.

        Sin filtro: todas las de proyectos activos. Con proyecto_id: solo las suyas.
        """
        hoy = date.today()
        if proyecto_id:
            _obtener(repo.proyectos, proyecto_id, "Proyecto")
            tareas = repo.tareas_de(proyecto_id)
        else:
            tareas = repo.tareas_de_activos()
        tareas = sorted(tareas, key=lambda t: (t.fecha_fin, t.fecha_inicio))
        return {"tareas": [_tarea_expandida(t, hoy) for t in tareas]}

    @app.post("/api/proyectos/{pid}/tareas")
    def crear_tarea(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        tarea = Tarea.model_validate({**datos, "proyecto_id": pid})
        repo.tareas[tarea.id] = tarea
        repo.guardar()
        return _tarea_expandida(tarea, date.today())

    @app.patch("/api/tareas/{tid}")
    def editar_tarea(tid: str, cambios: dict):
        tarea = _obtener(repo.tareas, tid, "Tarea")
        repo.tareas[tid] = _aplicar_cambios(tarea, cambios)
        repo.guardar()
        return _tarea_expandida(repo.tareas[tid], date.today())

    @app.delete("/api/tareas/{tid}")
    def borrar_tarea(tid: str):
        _obtener(repo.tareas, tid, "Tarea")
        del repo.tareas[tid]
        repo.guardar()
        return {"ok": True}

    # ----- Retos -----

    @app.post("/api/proyectos/{pid}/retos")
    def crear_reto(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        reto = Reto.model_validate({**datos, "proyecto_id": pid})
        repo.retos[reto.id] = reto
        repo.guardar()
        return reto.model_dump(mode="json")

    @app.patch("/api/retos/{rid}")
    def editar_reto(rid: str, cambios: dict):
        reto = _obtener(repo.retos, rid, "Reto")
        repo.retos[rid] = _aplicar_cambios(reto, cambios)
        repo.guardar()
        return repo.retos[rid].model_dump(mode="json")

    # ----- Hoy (método Ivy Lee) -----

    @app.get("/api/hoy")
    def hoy_():
        hoy = date.today()
        _asegurar_snapshots(hoy)
        plan = repo.plan_de(hoy)
        if plan is None:
            plan = PlanDia(fecha=hoy, tarea_ids=sugerir_plan_dia(repo.tareas_de_activos(), hoy))
            repo.poner_plan(plan)
            repo.guardar()

        tareas_plan = [
            _tarea_expandida(repo.tareas[tid], hoy)
            for tid in plan.tarea_ids if tid in repo.tareas
        ]
        candidatas = [
            _tarea_expandida(t, hoy)
            for t in sorted(repo.tareas_de_activos(), key=lambda t: t.fecha_fin)
            if t.estado in ("pendiente", "en_curso") and t.id not in plan.tarea_ids
        ]
        retos_abiertos = [
            {**r.model_dump(mode="json"),
             "proyecto_nombre": repo.proyectos[r.proyecto_id].nombre,
             "puntaje": r.impacto * r.probabilidad}
            for r in repo.retos.values()
            if r.estado == "abierto" and r.proyecto_id in {p.id for p in repo.proyectos_activos()}
        ]
        retos_abiertos.sort(key=lambda r: -r["puntaje"])

        return {
            "fecha": hoy.isoformat(),
            "cerrado": plan.cerrado,
            "nota_cierre": plan.nota_cierre,
            "tareas": tareas_plan,
            "candidatas": candidatas,
            "retos_arden": retos_abiertos[:3],
        }

    @app.put("/api/hoy")
    def poner_plan_hoy(cuerpo: CuerpoPlan):
        hoy = date.today()
        try:
            ids = validar_plan(cuerpo.tarea_ids)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        for tid in ids:
            if tid not in repo.tareas:
                raise HTTPException(status_code=404, detail=f"Tarea {tid} no existe")
        plan = repo.plan_de(hoy) or PlanDia(fecha=hoy)
        plan.tarea_ids = ids
        repo.poner_plan(plan)
        repo.guardar()
        return {"ok": True, "tarea_ids": ids}

    @app.post("/api/hoy/cerrar")
    def cerrar_dia(cuerpo: CuerpoCierre):
        hoy = date.today()
        plan = repo.plan_de(hoy)
        if plan is None:
            raise HTTPException(status_code=404, detail="Hoy no tiene plan que cerrar")
        plan.cerrado = True
        plan.nota_cierre = cuerpo.nota
        repo.poner_plan(plan)
        repo.guardar()
        pendientes = [tid for tid in plan.tarea_ids
                      if tid in repo.tareas and repo.tareas[tid].estado != "hecha"]
        return {"ok": True, "pendientes": len(pendientes)}

    # ----- Objetivos SMART -----

    def _validar(modelo_cls, datos: dict) -> Any:
        """Valida contra el modelo y traduce el error a un 422 legible."""
        try:
            return modelo_cls.model_validate(datos)
        except Exception as e:  # ValidationError
            errores = getattr(e, "errors", lambda: [{"msg": str(e)}])()
            detalle = "; ".join(
                f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg', '')}"
                for err in errores
            )
            raise HTTPException(status_code=422, detail=detalle)

    @app.post("/api/proyectos/{pid}/objetivos")
    def crear_objetivo(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        objetivo = _validar(Objetivo, {**datos, "proyecto_id": pid})
        repo.objetivos[objetivo.id] = objetivo
        repo.guardar()
        return objetivo.model_dump(mode="json")

    @app.patch("/api/objetivos/{oid}")
    def editar_objetivo(oid: str, cambios: dict):
        objetivo = _obtener(repo.objetivos, oid, "Objetivo")
        repo.objetivos[oid] = _validar(Objetivo, {**objetivo.model_dump(), **cambios})
        repo.guardar()
        return repo.objetivos[oid].model_dump(mode="json")

    @app.delete("/api/objetivos/{oid}")
    def borrar_objetivo(oid: str):
        _obtener(repo.objetivos, oid, "Objetivo")
        del repo.objetivos[oid]
        repo.guardar()
        return {"ok": True}

    # ----- Documentos estratégicos (JSONB versionado, CLAUDE.md §5) -----

    @app.get("/api/documentos")
    def listar_documentos(proyecto_id: Optional[str] = None):
        docs = list(repo.documentos.values())
        if proyecto_id:
            _obtener(repo.proyectos, proyecto_id, "Proyecto")
            docs = [d for d in docs if d.proyecto_id == proyecto_id]
        docs.sort(key=lambda d: d.creado_en)
        return {"documentos": [d.model_dump(mode="json") for d in docs]}

    @app.post("/api/documentos")
    def crear_documento(datos: dict):
        if datos.get("proyecto_id"):
            _obtener(repo.proyectos, datos["proyecto_id"], "Proyecto")
        doc = _validar(Documento, datos)
        repo.documentos[doc.id] = doc
        repo.guardar()
        return doc.model_dump(mode="json")

    @app.put("/api/documentos/{did}")
    def versionar_documento(did: str, datos: dict):
        """Guardar = nueva versión; la anterior queda en el historial."""
        doc = _obtener(repo.documentos, did, "Documento")
        doc.historial.append({
            "version": doc.version,
            "contenido": doc.contenido,
            "fecha": date.today().isoformat(),
        })
        doc.contenido = datos.get("contenido", {})
        doc.version += 1
        repo.guardar()
        return doc.model_dump(mode="json")

    @app.delete("/api/documentos/{did}")
    def borrar_documento(did: str):
        _obtener(repo.documentos, did, "Documento")
        del repo.documentos[did]
        repo.guardar()
        return {"ok": True}

    @app.post("/api/documentos/{did}/sembrar")
    def sembrar_charter(did: str):
        """El charter no es papel muerto: sus hitos de alto nivel se convierten
        en tareas-hito reales del proyecto (idempotente por título)."""
        doc = _obtener(repo.documentos, did, "Documento")
        if doc.tipo != "charter" or not doc.proyecto_id:
            raise HTTPException(status_code=400, detail="Solo un charter de proyecto puede sembrar el plan")
        hitos = [
            h for h in doc.contenido.get("hitos_alto_nivel", [])
            if h.get("titulo", "").strip() and h.get("fecha")
        ]
        if not hitos:
            raise HTTPException(status_code=400, detail="El charter no tiene hitos con título y fecha")
        existentes = {
            t.titulo.strip().lower()
            for t in repo.tareas_de(doc.proyecto_id) if t.es_hito
        }
        creados = 0
        for h in hitos:
            if h["titulo"].strip().lower() in existentes:
                continue
            tarea = _validar(Tarea, {
                "proyecto_id": doc.proyecto_id,
                "titulo": h["titulo"].strip(),
                "fecha_inicio": h["fecha"],
                "fecha_fin": h["fecha"],
                "es_hito": True,
                "importante": True,
                "esfuerzo_estimado_h": 0,
            })
            repo.tareas[tarea.id] = tarea
            creados += 1
        doc.contenido["sembrado"] = True
        doc.contenido["confirmado"] = True
        repo.guardar()
        return {"ok": True, "hitos_creados": creados, "hitos_existentes": len(hitos) - creados}

    # ----- Demo -----

    @app.post("/api/demo/sembrar")
    def sembrar_demo():
        if not repo.vacio():
            raise HTTPException(status_code=409, detail="Ya hay datos; la demo no los pisa")
        datos_demo.sembrar(repo)
        return {"ok": True, "proyectos": len(repo.proyectos)}

    app.state.repo = repo
    return app


app = crear_app()
