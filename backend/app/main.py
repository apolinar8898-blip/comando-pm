"""API de Comando PM (FastAPI).

El frontend no calcula reglas de negocio: todo KPI, semáforo y sugerencia
sale de aquí, que a su vez delega en el paquete dominio/ (lógica pura).
"""
from __future__ import annotations

import os
import secrets
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import datos_demo
from .captacion_api import ServicioCaptacion, montar_captacion
from .dominio.captacion import peor
from .dominio import (
    acciones_prospeccion,
    avance,
    componer_plan,
    cuadrante_eisenhower,
    fechas_a_generar,
    instancia,
    proximo_hito,
    ruta_critica,
    rutina_expirada,
    salud_proyecto,
    spi,
    sugerir_plan_dia,
    tareas_vencidas,
    validar_plan,
)
from .modelos import Documento, KpiSnapshot, Objetivo, PlanDia, Proyecto, Reto, Rutina, Tarea
from .reloj import hoy_local
from .repositorio import Repositorio, crear_repositorio


# ---------- Seguridad mínima (un solo usuario) ----------

def _verificar_token(x_token: Optional[str] = Header(default=None)) -> None:
    esperado = os.environ.get("APP_PASSWORD")
    if esperado and not secrets.compare_digest(x_token or "", esperado):
        raise HTTPException(status_code=401, detail="Token inválido")


# Un candado por petición a la API: los endpoints corren en un threadpool y
# mutan/guardan el mismo almacén; serializarlos elimina carreras y escrituras
# concurrentes al archivo. threading.Lock (no RLock): puede liberarse desde
# otro hilo del pool, cosa que el teardown de la dependencia puede necesitar.
CANDADO = threading.Lock()


def _candado():
    CANDADO.acquire()
    try:
        yield
    finally:
        CANDADO.release()


# ---------- Cuerpos de petición ----------

class CuerpoPlan(BaseModel):
    tarea_ids: list[str]


class CuerpoCierre(BaseModel):
    nota: str = ""


# ---------- Fábrica de la app (inyectable para tests) ----------

def crear_app(repo: Optional[Repositorio] = None) -> FastAPI:
    repo = repo if repo is not None else crear_repositorio()
    app = FastAPI(title="Comando PM")
    # El token y el candado gatean SOLO la API; la SPA estática se sirve libre.
    api = APIRouter(dependencies=[Depends(_verificar_token), Depends(_candado)])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----- Helpers -----

    captacion = ServicioCaptacion(repo)

    def _kpis(proyecto: Proyecto, hoy: date) -> dict[str, Any]:
        tareas = repo.tareas_de(proyecto.id)
        retos = repo.retos_de(proyecto.id)
        hito = proximo_hito(tareas, hoy)
        salud = salud_proyecto(tareas, retos, hoy)
        salud_extra = captacion.salud(proyecto, hoy)  # SINPROTEK: KPIs de captación
        return {
            "salud": peor(salud, salud_extra) if salud_extra else salud,
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

    def _materializar_rutinas(hoy: date) -> None:
        """Cada rutina de proyecto activo genera la tarea real de sus días (≤ hoy)."""
        activos = {p.id for p in repo.proyectos_activos()}
        cambio = False
        for rutina in repo.rutinas.values():
            if rutina.proyecto_id not in activos:
                continue
            fechas = fechas_a_generar(rutina, hoy)
            for fecha in fechas:
                tarea = instancia(rutina, fecha)
                repo.tareas[tarea.id] = tarea
            if fechas:
                rutina.generada_hasta = fechas[-1]
                cambio = True
        if cambio:
            repo.guardar()

    def _al_dia(hoy: date) -> None:
        """Rutinas primero (sus tareas cuentan en los KPIs), luego la foto del día."""
        _materializar_rutinas(hoy)
        if captacion.sincronizar_objetivo():
            repo.guardar()
        _asegurar_snapshots(hoy)

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
            "expirada": rutina_expirada(tarea, hoy),
            "proyecto_nombre": proyecto.nombre if proyecto else "?",
            "proyecto_color": proyecto.color if proyecto else "#888",
        }

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

    # Campos que un PATCH jamás puede tocar: mutarlos rompe las referencias
    # (claves de dicts, dependencias, origen_rca) de forma silenciosa.
    INMUTABLES = {"id", "proyecto_id", "creado_en"}

    def _aplicar_cambios(modelo: BaseModel, cambios: dict) -> Any:
        limpios = {k: v for k, v in cambios.items() if k not in INMUTABLES}
        return _validar(type(modelo), {**modelo.model_dump(), **limpios})

    def _obtener(coleccion: dict, id_: str, nombre: str) -> Any:
        item = coleccion.get(id_)
        if item is None:
            raise HTTPException(status_code=404, detail=f"{nombre} no encontrado")
        return item

    # ----- Salud del servicio -----

    @api.get("/api/salud")
    def salud_servicio():
        return {"ok": True, "proyectos": len(repo.proyectos)}

    # ----- Portafolio y proyectos -----

    @api.get("/api/portafolio")
    def portafolio():
        hoy = hoy_local()
        _al_dia(hoy)
        return {
            "proyectos": [
                {**p.model_dump(mode="json"), "kpis": _kpis(p, hoy)}
                for p in sorted(
                    repo.proyectos.values(),
                    key=lambda x: (x.estado != "activo", x.prioridad, x.fecha_fin_objetivo),
                )
            ]
        }

    @api.post("/api/proyectos")
    def crear_proyecto(datos: dict):
        proyecto = _validar(Proyecto, datos)
        repo.proyectos[proyecto.id] = proyecto
        repo.guardar()
        return proyecto.model_dump(mode="json")

    @api.get("/api/proyectos/{pid}")
    def detalle_proyecto(pid: str):
        hoy = hoy_local()
        proyecto = _obtener(repo.proyectos, pid, "Proyecto")
        _materializar_rutinas(hoy)
        tareas = sorted(repo.tareas_de(pid), key=lambda t: (t.fecha_inicio, t.fecha_fin))
        return {
            "proyecto": proyecto.model_dump(mode="json"),
            "kpis": _kpis(proyecto, hoy),
            "tareas": [_tarea_expandida(t, hoy) for t in tareas],
            "ruta_critica": sorted(ruta_critica(tareas)),
            "retos": [r.model_dump(mode="json") for r in repo.retos_de(pid)],
            "objetivos": [o.model_dump(mode="json") for o in repo.objetivos_de(pid)],
            "snapshots": [s.model_dump(mode="json") for s in repo.snapshots_de(pid)],
            "rutinas": [r.model_dump(mode="json") for r in repo.rutinas.values() if r.proyecto_id == pid],
        }

    @api.patch("/api/proyectos/{pid}")
    def editar_proyecto(pid: str, cambios: dict):
        proyecto = _obtener(repo.proyectos, pid, "Proyecto")
        repo.proyectos[pid] = _aplicar_cambios(proyecto, cambios)
        repo.guardar()
        return repo.proyectos[pid].model_dump(mode="json")

    # ----- Tareas -----

    @api.get("/api/tareas")
    def listar_tareas(proyecto_id: Optional[str] = None):
        """Tareas expandidas (con cuadrante y proyecto) para Eisenhower y plan semanal.

        Sin filtro: todas las de proyectos activos. Con proyecto_id: solo las suyas.
        """
        hoy = hoy_local()
        _materializar_rutinas(hoy)
        if proyecto_id:
            _obtener(repo.proyectos, proyecto_id, "Proyecto")
            tareas = repo.tareas_de(proyecto_id)
        else:
            tareas = repo.tareas_de_activos()
        tareas = sorted(tareas, key=lambda t: (t.fecha_fin, t.fecha_inicio))
        return {"tareas": [_tarea_expandida(t, hoy) for t in tareas]}

    @api.post("/api/proyectos/{pid}/tareas")
    def crear_tarea(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        tarea = _validar(Tarea, {**datos, "proyecto_id": pid})
        repo.tareas[tarea.id] = tarea
        repo.guardar()
        return _tarea_expandida(tarea, hoy_local())

    @api.patch("/api/tareas/{tid}")
    def editar_tarea(tid: str, cambios: dict):
        tarea = _obtener(repo.tareas, tid, "Tarea")
        repo.tareas[tid] = _aplicar_cambios(tarea, cambios)
        prospecto = repo.prospectos.get(tarea.prospecto_id or "")
        if prospecto and repo.tareas[tid].estado == "hecha":
            # La acción ya se hizo: el prospecto queda sin próxima acción
            # (lo ideal es "Registrar" la interacción, que agenda la siguiente).
            repo.prospectos[prospecto.id] = prospecto.model_copy(
                update={"proxima_accion": "", "fecha_proxima_accion": None})
        repo.guardar()
        return _tarea_expandida(repo.tareas[tid], hoy_local())

    @api.delete("/api/tareas/{tid}")
    def borrar_tarea(tid: str):
        _obtener(repo.tareas, tid, "Tarea")
        del repo.tareas[tid]
        repo.guardar()
        return {"ok": True}

    # ----- Retos -----

    @api.post("/api/proyectos/{pid}/retos")
    def crear_reto(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        reto = _validar(Reto, {**datos, "proyecto_id": pid})
        repo.retos[reto.id] = reto
        repo.guardar()
        return reto.model_dump(mode="json")

    @api.patch("/api/retos/{rid}")
    def editar_reto(rid: str, cambios: dict):
        reto = _obtener(repo.retos, rid, "Reto")
        repo.retos[rid] = _aplicar_cambios(reto, cambios)
        repo.guardar()
        return repo.retos[rid].model_dump(mode="json")

    # ----- Hoy (método Ivy Lee) -----

    @api.get("/api/hoy")
    def hoy_():
        hoy = hoy_local()
        _al_dia(hoy)
        plan = repo.plan_de(hoy)
        if plan is None:
            # Ivy Lee puro (§4.1): lo pendiente del último plan se arrastra al
            # frente de la sugerencia de hoy; el resto se completa hasta 6.
            ayer = repo.plan_de(hoy - timedelta(days=1))
            arrastradas = [
                tid for tid in (ayer.tarea_ids if ayer else [])
                if tid in repo.tareas and repo.tareas[tid].estado != "hecha"
                and not rutina_expirada(repo.tareas[tid], hoy)
            ]
            # Regla de Apo (Fase 1): acciones de prospección vencidas o de hoy primero.
            activas = repo.tareas_de_activos()
            ids = componer_plan(
                acciones_prospeccion(activas, hoy), arrastradas,
                sugerir_plan_dia(activas, hoy), captacion.tope_ivy(),
            )
            plan = PlanDia(fecha=hoy, tarea_ids=ids)
            repo.poner_plan(plan)
            repo.guardar()

        tareas_plan = [
            _tarea_expandida(repo.tareas[tid], hoy)
            for tid in plan.tarea_ids if tid in repo.tareas
        ]
        candidatas = [
            _tarea_expandida(t, hoy)
            for t in sorted(repo.tareas_de_activos(),
                            key=lambda t: (t.prospecto_id is None, t.fecha_fin))
            if t.estado in ("pendiente", "en_curso") and t.id not in plan.tarea_ids
            and not rutina_expirada(t, hoy)
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

    @api.put("/api/hoy")
    def poner_plan_hoy(cuerpo: CuerpoPlan):
        hoy = hoy_local()
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

    @api.post("/api/hoy/cerrar")
    def cerrar_dia(cuerpo: CuerpoCierre):
        hoy = hoy_local()
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

    # ----- Rutinas (trabajo recurrente) -----

    @api.post("/api/proyectos/{pid}/rutinas")
    def crear_rutina(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        rutina = _validar(Rutina, {"desde": hoy_local().isoformat(), **datos, "proyecto_id": pid})
        repo.rutinas[rutina.id] = rutina
        repo.guardar()
        return rutina.model_dump(mode="json")

    @api.patch("/api/rutinas/{rid}")
    def editar_rutina(rid: str, cambios: dict):
        """Nada se borra: una rutina que ya no aplica se desactiva (activa=false)."""
        rutina = _obtener(repo.rutinas, rid, "Rutina")
        cambios = {k: v for k, v in cambios.items() if k != "generada_hasta"}
        repo.rutinas[rid] = _aplicar_cambios(rutina, cambios)
        repo.guardar()
        return repo.rutinas[rid].model_dump(mode="json")

    # ----- Objetivos SMART -----

    @api.post("/api/proyectos/{pid}/objetivos")
    def crear_objetivo(pid: str, datos: dict):
        _obtener(repo.proyectos, pid, "Proyecto")
        objetivo = _validar(Objetivo, {**datos, "proyecto_id": pid})
        repo.objetivos[objetivo.id] = objetivo
        repo.guardar()
        return objetivo.model_dump(mode="json")

    @api.patch("/api/objetivos/{oid}")
    def editar_objetivo(oid: str, cambios: dict):
        objetivo = _obtener(repo.objetivos, oid, "Objetivo")
        repo.objetivos[oid] = _aplicar_cambios(objetivo, cambios)
        repo.guardar()
        return repo.objetivos[oid].model_dump(mode="json")

    @api.delete("/api/objetivos/{oid}")
    def borrar_objetivo(oid: str):
        _obtener(repo.objetivos, oid, "Objetivo")
        del repo.objetivos[oid]
        repo.guardar()
        return {"ok": True}

    # ----- Documentos estratégicos (JSONB versionado, CLAUDE.md §5) -----

    @api.get("/api/documentos")
    def listar_documentos(proyecto_id: Optional[str] = None):
        docs = list(repo.documentos.values())
        if proyecto_id:
            _obtener(repo.proyectos, proyecto_id, "Proyecto")
            docs = [d for d in docs if d.proyecto_id == proyecto_id]
        docs.sort(key=lambda d: d.creado_en)
        return {"documentos": [d.model_dump(mode="json") for d in docs]}

    @api.post("/api/documentos")
    def crear_documento(datos: dict):
        if datos.get("proyecto_id"):
            _obtener(repo.proyectos, datos["proyecto_id"], "Proyecto")
        doc = _validar(Documento, datos)
        repo.documentos[doc.id] = doc
        repo.guardar()
        return doc.model_dump(mode="json")

    @api.put("/api/documentos/{did}")
    def versionar_documento(did: str, datos: dict):
        """Guardar = nueva versión; la anterior queda en el historial."""
        doc = _obtener(repo.documentos, did, "Documento")
        doc.historial.append({
            "version": doc.version,
            "contenido": doc.contenido,
            "fecha": hoy_local().isoformat(),
        })
        doc.contenido = datos.get("contenido", {})
        doc.version += 1
        repo.guardar()
        return doc.model_dump(mode="json")

    @api.delete("/api/documentos/{did}")
    def borrar_documento(did: str):
        _obtener(repo.documentos, did, "Documento")
        del repo.documentos[did]
        repo.guardar()
        return {"ok": True}

    @api.post("/api/documentos/{did}/sembrar")
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

    @api.post("/api/documentos/{did}/sembrar-acciones")
    def sembrar_acciones_rca(did: str):
        """El RCA debe terminar en tareas, no en un PDF (CLAUDE.md §9):
        cada acción correctiva y la señal de verificación se vuelven tareas
        reales del proyecto, marcadas con origen_rca (idempotente por título)."""
        doc = _obtener(repo.documentos, did, "Documento")
        if doc.tipo != "rca" or not doc.proyecto_id:
            raise HTTPException(status_code=400, detail="Solo un RCA de proyecto puede crear acciones")

        acciones = [
            a for a in doc.contenido.get("acciones", [])
            if a.get("titulo", "").strip() and a.get("fecha")
        ]
        verificacion = doc.contenido.get("verificacion") or {}
        pendientes: list[tuple[str, str, str]] = [  # (titulo, fecha, clave)
            (a["titulo"].strip(), a["fecha"], "accion") for a in acciones
        ]
        if verificacion.get("senal", "").strip() and verificacion.get("fecha"):
            pendientes.append(
                (f"Verificar: {verificacion['senal'].strip()}", verificacion["fecha"], "verificacion")
            )
        if not pendientes:
            raise HTTPException(
                status_code=400,
                detail="El RCA no tiene acciones ni señal de verificación con fecha",
            )

        existentes = {
            t.titulo.strip().lower()
            for t in repo.tareas_de(doc.proyecto_id) if t.origen_rca == did
        }
        creadas = 0
        for titulo, fecha, _ in pendientes:
            if titulo.lower() in existentes:
                continue
            tarea = _validar(Tarea, {
                "proyecto_id": doc.proyecto_id,
                "titulo": titulo,
                "fecha_inicio": fecha,
                "fecha_fin": fecha,
                "importante": True,
                "esfuerzo_estimado_h": 1,
                "origen_rca": did,
            })
            repo.tareas[tarea.id] = tarea
            creadas += 1
        doc.contenido["acciones_sembradas"] = True
        repo.guardar()
        return {"ok": True, "tareas_creadas": creadas, "ya_existian": len(pendientes) - creadas}

    # ----- Export de respaldo (CLAUDE.md §9: sin backup no hay confianza) -----

    @api.get("/api/export")
    def exportar():
        nombre = f"comando-pm-export-{hoy_local().isoformat()}.json"
        return JSONResponse(
            repo.volcado(),
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
        )

    # ----- Demo -----

    @api.post("/api/demo/sembrar")
    def sembrar_demo():
        if not repo.vacio():
            raise HTTPException(status_code=409, detail="Ya hay datos; la demo no los pisa")
        datos_demo.sembrar(repo)
        return {"ok": True, "proyectos": len(repo.proyectos)}

    montar_captacion(app, api, repo, captacion, _validar, _candado)
    app.include_router(api)

    @app.get("/api/ping", include_in_schema=False)
    def ping():
        """Público y sin datos: para el healthcheck de Railway."""
        return {"ok": True}

    # ----- SPA compilada (arranque de un solo proceso) -----
    # Si existe frontend/dist (npm run build), FastAPI la sirve en / y la app
    # completa vive en http://localhost:8000 sin necesidad de Vite.
    dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{ruta:path}", include_in_schema=False)
        def spa(ruta: str):
            archivo = dist / ruta
            if ruta and archivo.is_file():
                return FileResponse(archivo)
            return FileResponse(dist / "index.html")

    app.state.repo = repo
    return app


app = crear_app()
