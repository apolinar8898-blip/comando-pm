"""API de Captación SINPROTEK (Fase 1): CRM de prospectos + endpoint de Alex.

La lógica de negocio vive en dominio/captacion.py; aquí solo se orquesta
el almacén: registrar interacciones, mover etapas y mantener sincronizada
la tarea de la próxima acción (que Ivy Lee pone antes que todo).
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import date, timedelta
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

from .dominio.captacion import (
    EMBUDO,
    META_SEMANA_DEFECTO,
    PROBABILIDAD_DEFECTO,
    alertas,
    cambiar_etapa,
    kpis_captacion,
    montos_por_segmento,
    normalizar_telefono,
    salud_captacion,
    tarea_de_accion,
    ultimo_contacto,
)
from .dominio.ivy_lee import MAX_TAREAS_DIA as TOPE_DEFECTO
from .modelos import Interaccion, Proyecto, Prospecto, Salud
from .reloj import ahora_local, hoy_local
from .repositorio import Repositorio

METRICA_CLIENTES = "clientes pagando"
CAMPOS_FIJOS = {"id", "creado", "fechas_etapa", "actualizado"}


class ServicioCaptacion:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    # ----- Configuración -----

    def meta_semana(self) -> int:
        return int(self.repo.configuracion.get("meta_interacciones_semana", META_SEMANA_DEFECTO))

    def probabilidades(self) -> dict[str, float]:
        return {**PROBABILIDAD_DEFECTO, **(self.repo.configuracion.get("probabilidad_etapa") or {})}

    def tope_ivy(self) -> int:
        return int(self.repo.configuracion.get("tope_prospeccion_ivy", TOPE_DEFECTO))

    # ----- KPIs y salud -----

    def kpis(self, hoy: date) -> dict:
        return kpis_captacion(
            list(self.repo.prospectos.values()), list(self.repo.interacciones.values()),
            hoy, self.meta_semana(), self.probabilidades(),
        )

    def salud(self, proyecto: Proyecto, hoy: date) -> Optional[Salud]:
        """Salud extra solo para el proyecto de captación (None para los demás)."""
        captacion = self.repo.proyecto_captacion()
        if captacion is None or captacion.id != proyecto.id:
            return None
        return salud_captacion(self.kpis(hoy))

    def sincronizar_objetivo(self) -> bool:
        """El objetivo SMART "clientes pagando" se calcula, no se captura."""
        captacion = self.repo.proyecto_captacion()
        if captacion is None:
            return False
        ganados = sum(1 for p in self.repo.prospectos.values() if p.etapa == "ganado")
        cambio = False
        for o in self.repo.objetivos_de(captacion.id):
            if o.metrica.strip().lower() == METRICA_CLIENTES and o.valor_actual != ganados:
                o.valor_actual = ganados
                cambio = True
        return cambio

    # ----- Próxima acción ↔ tarea -----

    def sincronizar_accion(self, p: Prospecto) -> None:
        """Una tarea abierta por prospecto activo con próxima acción; ninguna si no.
        La tarea es una proyección del prospecto: si ya no aplica, se quita."""
        captacion = self.repo.proyecto_captacion()
        pendiente = self.repo.accion_pendiente(p.id)
        if captacion is None:
            return
        nueva = tarea_de_accion(p, pendiente, captacion.id)
        if nueva is None:
            if pendiente is not None:
                del self.repo.tareas[pendiente.id]
            return
        self.repo.tareas[nueva.id] = nueva

    # ----- Registrar interacción -----

    def registrar(
        self, p: Prospecto, canal: str, resultado: str, nota: str, hoy: date,
        proxima_accion: str = "", fecha_proxima: Optional[date] = None,
    ) -> Interaccion:
        """Registra la interacción, cierra la acción que estaba pendiente y
        programa la siguiente (o ninguna). Contactar a un "identificado" lo
        mueve a "contactado"."""
        interaccion = Interaccion(prospecto_id=p.id, canal=canal, resultado=resultado, nota=nota)
        self.repo.interacciones[interaccion.id] = interaccion

        pendiente = self.repo.accion_pendiente(p.id)
        if pendiente is not None:
            pendiente.estado = "hecha"

        if p.etapa == "identificado":
            p = cambiar_etapa(p, "contactado", hoy)
        p = p.model_copy(update={
            "proxima_accion": proxima_accion.strip(),
            "fecha_proxima_accion": fecha_proxima,
            "actualizado": ahora_local(),
        })
        self.repo.prospectos[p.id] = p
        self.sincronizar_accion(p)
        return interaccion

    def expandido(self, p: Prospecto, hoy: date) -> dict[str, Any]:
        propias = [i for i in self.repo.interacciones.values() if i.prospecto_id == p.id]
        ultimo = ultimo_contacto(p, propias)
        return {
            **p.model_dump(mode="json"),
            "alertas": alertas(p, propias, hoy),
            "ultimo_contacto": ultimo.isoformat(),
            "dias_sin_contacto": (hoy - ultimo).days,
            "num_interacciones": len(propias),
        }


def _fecha(valor: Any) -> Optional[date]:
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"fecha inválida: {valor}")


def montar_captacion(
    app: FastAPI, api: APIRouter, repo: Repositorio, servicio: ServicioCaptacion,
    validar: Callable, candado: Callable,
) -> None:
    """Rutas de captación en el router protegido + el endpoint de Alex (token propio)."""

    def _prospecto(pid: str) -> Prospecto:
        p = repo.prospectos.get(pid)
        if p is None:
            raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        return p

    def _con_422(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except ValueError as e:  # incluye ValidationError de Pydantic
            raise HTTPException(status_code=422, detail=str(e).split("\n")[-1].strip() or str(e))

    @api.get("/api/captacion")
    def tablero():
        hoy = hoy_local()
        prospectos = sorted(repo.prospectos.values(), key=lambda p: p.actualizado, reverse=True)
        return {
            "kpis": servicio.kpis(hoy),
            "prospectos": [servicio.expandido(p, hoy) for p in prospectos],
            "embudo": EMBUDO,
            "config": {
                "meta_interacciones_semana": servicio.meta_semana(),
                "probabilidad_etapa": servicio.probabilidades(),
                "tope_prospeccion_ivy": servicio.tope_ivy(),
            },
        }

    @api.post("/api/captacion/prospectos")
    def crear_prospecto(datos: dict):
        hoy = hoy_local()
        segmento = datos.get("segmento") or "pyme"
        if segmento not in ("pyme", "independiente"):
            raise HTTPException(status_code=422, detail="segmento: pyme o independiente")
        desarrollo, mensual = montos_por_segmento(segmento)
        etapa = datos.get("etapa") or "identificado"
        p = validar(Prospecto, {
            "monto_desarrollo": desarrollo, "monto_mensual": mensual,
            **{k: v for k, v in datos.items() if k not in CAMPOS_FIJOS},
            "segmento": segmento, "etapa": etapa, "fechas_etapa": {etapa: hoy.isoformat()},
        })
        repo.prospectos[p.id] = p
        servicio.sincronizar_accion(p)
        servicio.sincronizar_objetivo()
        repo.guardar()
        return servicio.expandido(p, hoy)

    @api.get("/api/captacion/prospectos/{pid}")
    def ficha(pid: str):
        hoy = hoy_local()
        p = _prospecto(pid)
        return {
            "prospecto": servicio.expandido(p, hoy),
            "interacciones": [i.model_dump(mode="json") for i in repo.interacciones_de(pid)],
        }

    @api.patch("/api/captacion/prospectos/{pid}")
    def editar_prospecto(pid: str, cambios: dict):
        hoy = hoy_local()
        p = _prospecto(pid)
        nueva_etapa = cambios.get("etapa", p.etapa)
        otros = {k: v for k, v in cambios.items() if k not in CAMPOS_FIJOS | {"etapa"}}
        base = validar(Prospecto, {**p.model_dump(), **otros, "etapa": p.etapa,
                                   "actualizado": ahora_local()})
        if nueva_etapa != p.etapa:
            base = _con_422(lambda: cambiar_etapa(base, nueva_etapa, hoy, cambios.get("motivo_perdida", "")))
        repo.prospectos[pid] = base
        servicio.sincronizar_accion(base)
        servicio.sincronizar_objetivo()
        repo.guardar()
        return servicio.expandido(base, hoy)

    @api.post("/api/captacion/prospectos/{pid}/interacciones")
    def registrar_interaccion(pid: str, datos: dict):
        hoy = hoy_local()
        p = _prospecto(pid)
        interaccion = _con_422(lambda: servicio.registrar(
            p, datos.get("canal", ""), datos.get("resultado", ""), datos.get("nota", ""), hoy,
            datos.get("proxima_accion", ""), _fecha(datos.get("fecha_proxima_accion")),
        ))
        repo.guardar()
        return {
            "interaccion": interaccion.model_dump(mode="json"),
            "prospecto": servicio.expandido(repo.prospectos[pid], hoy),
        }

    @api.put("/api/captacion/config")
    def configurar(datos: dict):
        if "meta_interacciones_semana" in datos:
            meta = int(datos["meta_interacciones_semana"])
            if meta < 1:
                raise HTTPException(status_code=422, detail="la meta semanal debe ser ≥ 1")
            repo.configuracion["meta_interacciones_semana"] = meta
        if "probabilidad_etapa" in datos:
            prob = {k: float(v) for k, v in datos["probabilidad_etapa"].items()}
            if any(k not in PROBABILIDAD_DEFECTO or not 0 <= v <= 1 for k, v in prob.items()):
                raise HTTPException(status_code=422, detail="probabilidades: etapas activas, entre 0 y 1")
            repo.configuracion["probabilidad_etapa"] = prob
        if "tope_prospeccion_ivy" in datos:
            tope = int(datos["tope_prospeccion_ivy"])
            if not 0 <= tope <= 6:
                raise HTTPException(status_code=422, detail="el tope va de 0 a 6")
            repo.configuracion["tope_prospeccion_ivy"] = tope
        repo.guardar()
        return {"ok": True}

    # ----- Alex (VAPI, tool registrar_resultado) — token propio -----

    def _verificar_alex(authorization: Optional[str] = Header(default=None)) -> None:
        esperado = os.environ.get("ALEX_TOKEN")
        if not esperado:
            raise HTTPException(status_code=503, detail="ALEX_TOKEN no configurado")
        recibido = (authorization or "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(recibido, esperado):
            raise HTTPException(status_code=401, detail="Token de Alex inválido")

    alex = APIRouter(dependencies=[Depends(_verificar_alex), Depends(candado)])

    def _registrar_alex(args: dict, telefono_llamada: str) -> str:
        hoy = hoy_local()
        telefono = str(args.get("telefono") or telefono_llamada or "")
        clave = normalizar_telefono(telefono)
        p = next((x for x in repo.prospectos.values()
                  if clave and normalizar_telefono(x.telefono) == clave), None)
        if p is None:
            desarrollo, mensual = montos_por_segmento("pyme")
            p = Prospecto(
                empresa=(args.get("empresa") or args.get("contacto") or f"Llamada {telefono}").strip(),
                contacto=args.get("contacto") or "", telefono=telefono, origen="llamada_alex",
                monto_desarrollo=desarrollo, monto_mensual=mensual,
                fechas_etapa={"identificado": hoy.isoformat()},
            )
            repo.prospectos[p.id] = p
        else:
            p = p.model_copy(update={
                "empresa": p.empresa if p.empresa and not p.empresa.startswith("Llamada ")
                else (args.get("empresa") or p.empresa),
                "contacto": p.contacto or args.get("contacto") or "",
            })
            repo.prospectos[p.id] = p

        if args.get("agendo_cita"):
            fecha = _fecha(args.get("fecha_cita")) or hoy + timedelta(days=1)
            accion = "Reunión agendada por Alex"
        else:
            fecha, accion = hoy + timedelta(days=2), "Seguimiento de llamada de Alex"
        servicio.registrar(p, "alex", str(args.get("resultado") or ""), str(args.get("nota") or ""),
                           hoy, accion, fecha)
        p = repo.prospectos[p.id]
        agendo = bool(args.get("agendo_cita"))
        if agendo and p.etapa in EMBUDO and EMBUDO.index(p.etapa) < EMBUDO.index("reunion_agendada"):
            repo.prospectos[p.id] = cambiar_etapa(p, "reunion_agendada", hoy)
        servicio.sincronizar_objetivo()
        repo.guardar()
        return f"Registrado: {repo.prospectos[p.id].empresa}, próxima acción {fecha.strftime('%d/%m/%Y')}."

    @alex.post("/api/captacion/alex")
    def registrar_desde_alex(cuerpo: dict):
        """Acepta el formato tool-calls de VAPI o un JSON plano (para pruebas).
        Responde {"results": [{"toolCallId", "result"}]} como espera VAPI."""
        mensaje = cuerpo.get("message") or {}
        llamadas = mensaje.get("toolCallList") or mensaje.get("toolCalls")
        telefono_llamada = ((mensaje.get("call") or {}).get("customer") or {}).get("number", "")
        if not llamadas:
            return {"results": [{"toolCallId": None, "result": _registrar_alex(cuerpo, "")}]}
        resultados = []
        for llamada in llamadas:
            funcion = llamada.get("function") or {}
            args = funcion.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            try:
                texto = _registrar_alex(args, telefono_llamada)
            except (ValueError, HTTPException) as e:
                texto = f"No se pudo registrar: {getattr(e, 'detail', e)}"
            resultados.append({"toolCallId": llamada.get("id"), "result": texto})
        return {"results": resultados}

    app.include_router(alex)
