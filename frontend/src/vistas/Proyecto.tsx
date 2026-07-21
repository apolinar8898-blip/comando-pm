import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { DetalleProyecto, EstadoTarea } from "../tipos";
import Semaforo from "../componentes/Semaforo";
import { fechaCorta } from "../componentes/Chips";
import Documentos from "../componentes/Documentos";
import Gantt from "../componentes/Gantt";
import GraficaAvance from "../componentes/GraficaAvance";
import Retos from "../componentes/Retos";
import Eisenhower from "./Eisenhower";
import Semana from "./Semana";

type Pestana = "dashboard" | "gantt" | "semana" | "eisenhower" | "tareas" | "retos" | "docs";

export default function Proyecto() {
  const { id } = useParams<{ id: string }>();
  const [detalle, setDetalle] = useState<DetalleProyecto | null>(null);
  const [pestana, setPestana] = useState<Pestana>("dashboard");

  const cargar = useCallback(async () => {
    if (id) setDetalle(await api.get<DetalleProyecto>(`/api/proyectos/${id}`));
  }, [id]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!detalle) return <p className="text-sm text-[var(--tinta-suave)]">Cargando…</p>;
  const { proyecto, kpis, tareas, retos, objetivos, snapshots, ruta_critica } = detalle;

  async function moverTarea(tid: string, fecha_inicio: string, fecha_fin: string) {
    await api.patch(`/api/tareas/${tid}`, { fecha_inicio, fecha_fin });
    await cargar();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Link to="/portafolio" className="text-xs text-[var(--acento)] hover:underline">
            ← Portafolio
          </Link>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <span className="h-3 w-3 rounded-full" style={{ background: proyecto.color }} />
            {proyecto.nombre}
            <Semaforo salud={kpis.salud} />
          </h1>
          {proyecto.descripcion && <p className="text-sm text-[var(--tinta-2)]">{proyecto.descripcion}</p>}
        </div>
        <nav className="flex gap-1 rounded-lg border border-[var(--borde)] bg-[var(--superficie)] p-1">
          {(["dashboard", "gantt", "semana", "eisenhower", "tareas", "retos", "docs"] as Pestana[]).map((p) => (
            <button
              key={p}
              onClick={() => setPestana(p)}
              className={`rounded-md px-3 py-1 text-sm capitalize ${pestana === p ? "bg-[var(--tinta)] text-white" : "text-[var(--tinta-2)] hover:bg-black/5"}`}
            >
              {p}
            </button>
          ))}
        </nav>
      </div>

      {pestana === "dashboard" && (
        <div className="space-y-4">
          {/* Fichas de KPIs */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Ficha titulo="Avance" valor={`${kpis.avance_pct}%`} />
            <Ficha titulo="SPI" valor={kpis.spi.toFixed(2)} alerta={kpis.spi < 0.95} detalle={kpis.spi < 0.95 ? "atrasado vs plan" : "en plan"} />
            <Ficha titulo="Vencidas" valor={String(kpis.tareas_vencidas)} alerta={kpis.tareas_vencidas > 0} />
            <Ficha titulo="Retos abiertos" valor={String(kpis.retos_abiertos)} />
            <Ficha titulo="Días para fin" valor={String(kpis.dias_para_fin)} alerta={kpis.dias_para_fin < 0} />
            <Ficha
              titulo="Próximo hito"
              valor={kpis.proximo_hito ? fechaCorta(kpis.proximo_hito.fecha) : "—"}
              detalle={kpis.proximo_hito?.titulo}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
            <GraficaAvance snapshots={snapshots} />
            <div className="space-y-4">
              {/* Objetivos SMART */}
              <div className="tarjeta p-4">
                <h3 className="mb-2 text-sm font-semibold">Objetivos SMART</h3>
                {objetivos.length === 0 && <p className="text-xs text-[var(--tinta-suave)]">Sin objetivos aún.</p>}
                {objetivos.map((o) => {
                  const pct = Math.min(100, (o.valor_actual / o.valor_objetivo) * 100);
                  return (
                    <div key={o.id} className="mb-3">
                      <p className="text-xs font-medium">{o.especifico}</p>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-black/10">
                        <div className="h-full rounded-full bg-[var(--acento)]" style={{ width: `${pct}%` }} />
                      </div>
                      <p className="mt-0.5 text-[10px] text-[var(--tinta-suave)]">
                        {o.metrica}: {o.valor_actual} / {o.valor_objetivo} · límite {fechaCorta(o.fecha_limite)}
                      </p>
                    </div>
                  );
                })}
              </div>
              {/* Retos */}
              <div className="tarjeta p-4">
                <h3 className="mb-2 text-sm font-semibold">Retos</h3>
                {retos.length === 0 && <p className="text-xs text-[var(--tinta-suave)]">Sin retos registrados.</p>}
                <ul className="space-y-2">
                  {retos.map((r) => (
                    <li key={r.id} className="border-l-4 pl-2" style={{ borderLeftColor: r.estado !== "abierto" ? "var(--eje)" : r.impacto * r.probabilidad >= 16 ? "var(--critico)" : r.impacto * r.probabilidad >= 9 ? "var(--alerta)" : "var(--ok)" }}>
                      <p className={`text-xs font-medium ${r.estado !== "abierto" ? "text-[var(--tinta-suave)] line-through" : ""}`}>{r.titulo}</p>
                      <p className="text-[10px] text-[var(--tinta-suave)]">
                        {r.tipo.replace("_", " ")} · impacto {r.impacto} × prob. {r.probabilidad} = {r.impacto * r.probabilidad}
                        {r.plan_de_respuesta && ` · plan: ${r.plan_de_respuesta}`}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {pestana === "gantt" && <Gantt tareas={tareas} rutaCritica={ruta_critica} onMover={moverTarea} />}

      {pestana === "semana" && <Semana proyectoId={proyecto.id} />}

      {pestana === "eisenhower" && <Eisenhower proyectoId={proyecto.id} />}

      {pestana === "tareas" && <TablaTareas detalle={detalle} recargar={cargar} />}

      {pestana === "retos" && <Retos detalle={detalle} recargar={cargar} irADocs={() => setPestana("docs")} />}

      {pestana === "docs" && <Documentos detalle={detalle} recargar={cargar} />}
    </div>
  );
}

function Ficha({ titulo, valor, detalle, alerta }: { titulo: string; valor: string; detalle?: string; alerta?: boolean }) {
  return (
    <div className="tarjeta px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wide text-[var(--tinta-suave)]">{titulo}</p>
      <p className={`text-lg font-bold ${alerta ? "text-[var(--critico)]" : ""}`}>{valor}</p>
      {detalle && <p className="truncate text-[10px] text-[var(--tinta-suave)]" title={detalle}>{detalle}</p>}
    </div>
  );
}

const ESTADOS: EstadoTarea[] = ["pendiente", "en_curso", "hecha", "bloqueada"];

function TablaTareas({ detalle, recargar }: { detalle: DetalleProyecto; recargar: () => Promise<void> }) {
  const hoyIso = new Date().toISOString().slice(0, 10);
  const [forma, setForma] = useState({ titulo: "", fecha_inicio: hoyIso, fecha_fin: hoyIso, esfuerzo_estimado_h: 2, importante: true, es_hito: false });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    const datos = forma.es_hito ? { ...forma, fecha_inicio: forma.fecha_fin, esfuerzo_estimado_h: 0 } : forma;
    await api.post(`/api/proyectos/${detalle.proyecto.id}/tareas`, datos);
    setForma({ ...forma, titulo: "" });
    await recargar();
  }

  async function cambiarEstado(tid: string, estado: string) {
    await api.patch(`/api/tareas/${tid}`, { estado });
    await recargar();
  }

  async function borrar(tid: string) {
    if (confirm("¿Borrar esta tarea?")) {
      await api.del(`/api/tareas/${tid}`);
      await recargar();
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={crear} className="tarjeta flex flex-wrap items-end gap-3 p-4">
        <label className="flex-1 text-xs text-[var(--tinta-2)]">
          Nueva tarea
          <input required value={forma.titulo} onChange={(e) => setForma({ ...forma, titulo: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm" placeholder="Título" />
        </label>
        {!forma.es_hito && (
          <label className="text-xs text-[var(--tinta-2)]">
            Inicio
            <input type="date" value={forma.fecha_inicio} onChange={(e) => setForma({ ...forma, fecha_inicio: e.target.value })} className="mt-1 block rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
          </label>
        )}
        <label className="text-xs text-[var(--tinta-2)]">
          {forma.es_hito ? "Fecha del hito" : "Fin"}
          <input type="date" value={forma.fecha_fin} onChange={(e) => setForma({ ...forma, fecha_fin: e.target.value })} className="mt-1 block rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
        </label>
        {!forma.es_hito && (
          <label className="text-xs text-[var(--tinta-2)]">
            Horas
            <input type="number" min={0.5} step={0.5} value={forma.esfuerzo_estimado_h} onChange={(e) => setForma({ ...forma, esfuerzo_estimado_h: Number(e.target.value) })} className="mt-1 block w-20 rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
          </label>
        )}
        <label className="flex items-center gap-1 pb-2 text-xs">
          <input type="checkbox" checked={forma.importante} onChange={(e) => setForma({ ...forma, importante: e.target.checked })} /> Importante
        </label>
        <label className="flex items-center gap-1 pb-2 text-xs">
          <input type="checkbox" checked={forma.es_hito} onChange={(e) => setForma({ ...forma, es_hito: e.target.checked })} /> ◆ Hito
        </label>
        <button type="submit" className="rounded-lg bg-[var(--tinta)] px-4 py-2 text-sm font-medium text-white">
          Agregar
        </button>
      </form>

      <div className="tarjeta overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--borde)] text-left text-[10px] uppercase tracking-wide text-[var(--tinta-suave)]">
              <th className="px-4 py-2">Tarea</th>
              <th className="px-2 py-2">Estado</th>
              <th className="px-2 py-2">Inicio</th>
              <th className="px-2 py-2">Fin</th>
              <th className="px-2 py-2">Horas</th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {detalle.tareas.map((t) => (
              <tr key={t.id} className="border-b border-[var(--grid)] last:border-0">
                <td className="px-4 py-2">
                  {t.es_hito && "◆ "}
                  <span className={t.estado === "hecha" ? "text-[var(--tinta-suave)] line-through" : ""}>{t.titulo}</span>
                  {t.importante && <span title="Importante"> ★</span>}
                  {detalle.ruta_critica.includes(t.id) && (
                    <span className="ml-1 rounded bg-black/10 px-1 text-[9px] font-semibold">CRÍTICA</span>
                  )}
                </td>
                <td className="px-2 py-2">
                  <select value={t.estado} onChange={(e) => cambiarEstado(t.id, e.target.value)} className="rounded border border-[var(--borde)] px-1 py-0.5 text-xs">
                    {ESTADOS.map((s) => (
                      <option key={s} value={s}>
                        {s.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-2 text-xs">{fechaCorta(t.fecha_inicio)}</td>
                <td className={`px-2 py-2 text-xs ${t.estado !== "hecha" && t.fecha_fin < new Date().toISOString().slice(0, 10) ? "font-semibold text-[var(--critico)]" : ""}`}>
                  {fechaCorta(t.fecha_fin)}
                </td>
                <td className="px-2 py-2 text-xs">{t.es_hito ? "—" : t.esfuerzo_estimado_h}</td>
                <td className="px-2 py-2">
                  <button onClick={() => borrar(t.id)} className="text-[var(--tinta-suave)] hover:text-[var(--critico)]" title="Borrar">
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
