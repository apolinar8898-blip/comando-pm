import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Proyecto } from "../tipos";
import Semaforo from "../componentes/Semaforo";
import { fechaCorta } from "../componentes/Chips";

// Portafolio: tarjetas con KPIs + roadmap de todos los proyectos (Gantt de 10,000 m).

export default function Portafolio() {
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [cargado, setCargado] = useState(false);
  const [creando, setCreando] = useState(false);
  const [forma, setForma] = useState({ nombre: "", fecha_inicio: "", fecha_fin_objetivo: "", color: "#4f46e5", prioridad: 3 });

  const cargar = useCallback(async () => {
    const r = await api.get<{ proyectos: Proyecto[] }>("/api/portafolio");
    setProyectos(r.proyectos);
    setCargado(true);
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function sembrarDemo() {
    await api.post("/api/demo/sembrar");
    await cargar();
  }

  async function crearProyecto(e: React.FormEvent) {
    e.preventDefault();
    await api.post("/api/proyectos", forma);
    setCreando(false);
    setForma({ ...forma, nombre: "" });
    await cargar();
  }

  async function exportarRespaldo() {
    // fetch directo (no api.get) para poder descargar el blob con su nombre
    const token = localStorage.getItem("comando_pm_token");
    const r = await fetch("/api/export", { headers: token ? { "X-Token": token } : {} });
    if (!r.ok) {
      window.dispatchEvent(new CustomEvent("api-error", { detail: "No se pudo exportar el respaldo" }));
      return;
    }
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `comando-pm-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const activos = proyectos.filter((p) => p.estado === "activo");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Portafolio</h1>
        <div className="flex gap-2">
          <button
            onClick={exportarRespaldo}
            title="Descarga todos los datos en un JSON (CLAUDE.md §9: sin backup no hay confianza)"
            className="rounded-lg border border-[var(--borde)] px-3 py-1.5 text-sm font-medium hover:bg-black/5"
          >
            ⬇ Respaldo
          </button>
          <button
            onClick={() => setCreando(!creando)}
            className="rounded-lg bg-[var(--tinta)] px-3 py-1.5 text-sm font-medium text-white"
          >
            + Nuevo proyecto
          </button>
        </div>
      </div>

      {creando && (
        <form onSubmit={crearProyecto} className="tarjeta grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
          <input
            required
            placeholder="Nombre del proyecto"
            value={forma.nombre}
            onChange={(e) => setForma({ ...forma, nombre: e.target.value })}
            className="rounded-lg border border-[var(--borde)] px-3 py-2 text-sm lg:col-span-2"
          />
          <label className="flex items-center gap-2 text-xs text-[var(--tinta-2)]">
            Inicio
            <input required type="date" value={forma.fecha_inicio} onChange={(e) => setForma({ ...forma, fecha_inicio: e.target.value })} className="flex-1 rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
          </label>
          <label className="flex items-center gap-2 text-xs text-[var(--tinta-2)]">
            Fin
            <input required type="date" value={forma.fecha_fin_objetivo} onChange={(e) => setForma({ ...forma, fecha_fin_objetivo: e.target.value })} className="flex-1 rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
          </label>
          <div className="flex items-center gap-2">
            <input type="color" value={forma.color} onChange={(e) => setForma({ ...forma, color: e.target.value })} className="h-9 w-9 rounded" aria-label="Color del proyecto" />
            <button type="submit" className="flex-1 rounded-lg bg-[var(--tinta)] px-3 py-2 text-sm font-medium text-white">
              Crear
            </button>
          </div>
        </form>
      )}

      {cargado && proyectos.length === 0 && (
        <div className="tarjeta p-8 text-center">
          <p className="mb-3 text-sm text-[var(--tinta-2)]">Aún no hay proyectos.</p>
          <button onClick={sembrarDemo} className="rounded-lg border border-[var(--borde)] px-3 py-1.5 text-sm font-medium hover:bg-black/5">
            Sembrar datos de demostración
          </button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {proyectos.map((p) => (
          <Link key={p.id} to={`/proyecto/${p.id}`} className="tarjeta block overflow-hidden hover:bg-black/[.02]">
            <div className="h-1.5" style={{ background: p.color }} />
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="font-semibold">{p.nombre}</h2>
                  <p className="text-xs text-[var(--tinta-suave)]">
                    {p.fase && `${p.fase} · `}
                    {p.estado !== "activo" ? p.estado : `termina ${fechaCorta(p.fecha_fin_objetivo)}`}
                  </p>
                </div>
                {p.kpis && <Semaforo salud={p.kpis.salud} />}
              </div>
              {p.kpis && (
                <>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/10">
                    <div className="h-full rounded-full" style={{ width: `${p.kpis.avance_pct}%`, background: p.color }} />
                  </div>
                  <dl className="mt-3 grid grid-cols-4 gap-2 text-center">
                    <Dato titulo="Avance" valor={`${p.kpis.avance_pct}%`} />
                    <Dato titulo="SPI" valor={p.kpis.spi.toFixed(2)} alerta={p.kpis.spi < 0.95} />
                    <Dato titulo="Vencidas" valor={String(p.kpis.tareas_vencidas)} alerta={p.kpis.tareas_vencidas > 0} />
                    <Dato titulo="Retos" valor={String(p.kpis.retos_abiertos)} />
                  </dl>
                  {p.kpis.proximo_hito && (
                    <p className="mt-3 text-xs text-[var(--tinta-2)]">
                      ◆ Próximo hito: <strong>{p.kpis.proximo_hito.titulo}</strong> · {fechaCorta(p.kpis.proximo_hito.fecha)}
                    </p>
                  )}
                </>
              )}
            </div>
          </Link>
        ))}
      </div>

      {/* Roadmap del portafolio */}
      {activos.length > 0 && <Roadmap proyectos={activos} />}
    </div>
  );
}

function Dato({ titulo, valor, alerta }: { titulo: string; valor: string; alerta?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-[var(--tinta-suave)]">{titulo}</dt>
      <dd className={`text-sm font-bold ${alerta ? "text-[var(--critico)]" : ""}`}>{valor}</dd>
    </div>
  );
}

const DIA_MS = 86_400_000;

function Roadmap({ proyectos }: { proyectos: Proyecto[] }) {
  const fechas = proyectos.flatMap((p) => [p.fecha_inicio, p.fecha_fin_objetivo]);
  const min = new Date(fechas.reduce((a, b) => (a < b ? a : b)) + "T00:00:00");
  const max = new Date(fechas.reduce((a, b) => (a > b ? a : b)) + "T00:00:00");
  min.setDate(1);
  max.setMonth(max.getMonth() + 1, 1);
  const total = (max.getTime() - min.getTime()) / DIA_MS;
  const pct = (iso: string) => (((new Date(iso + "T00:00:00").getTime() - min.getTime()) / DIA_MS) / total) * 100;
  const hoyPct = ((Date.now() - min.getTime()) / DIA_MS / total) * 100;

  const meses: { pct: number; texto: string }[] = [];
  const cursor = new Date(min);
  while (cursor < max) {
    meses.push({ pct: pct(cursor.toISOString().slice(0, 10)), texto: cursor.toLocaleDateString("es-MX", { month: "short" }) });
    cursor.setMonth(cursor.getMonth() + 1);
  }

  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-[var(--tinta-2)]">Roadmap</h2>
      <div className="tarjeta relative overflow-hidden p-4 pt-7">
        {meses.map((m) => (
          <div key={m.pct} className="absolute top-0 bottom-0 border-l border-[var(--grid)] pl-1 text-[9px] text-[var(--tinta-suave)]" style={{ left: `${m.pct}%` }}>
            {m.texto}
          </div>
        ))}
        {hoyPct >= 0 && hoyPct <= 100 && (
          <div className="absolute top-0 bottom-0 z-10 border-l-2 border-[var(--acento)]" style={{ left: `${hoyPct}%` }} />
        )}
        <div className="relative space-y-2">
          {proyectos.map((p) => (
            <div key={p.id} className="relative h-7">
              <Link
                to={`/proyecto/${p.id}`}
                className="absolute flex h-6 items-center truncate rounded-md px-2 text-[11px] font-medium text-white"
                style={{
                  left: `${pct(p.fecha_inicio)}%`,
                  width: `${Math.max(4, pct(p.fecha_fin_objetivo) - pct(p.fecha_inicio))}%`,
                  background: p.color,
                }}
              >
                {p.nombre}
                {p.fase && <span className="ml-1.5 font-normal opacity-75">· {p.fase}</span>}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
