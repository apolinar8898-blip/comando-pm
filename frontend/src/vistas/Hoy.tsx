import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Hoy as DatosHoy, Proyecto } from "../tipos";
import Semaforo from "../componentes/Semaforo";
import { ChipProyecto, EtiquetaCuadrante, fechaCorta } from "../componentes/Chips";

// La pantalla más importante de la app (CLAUDE.md §4.1):
// plan Ivy Lee del día, semáforo del portafolio y retos que arden.

export default function Hoy() {
  const [hoy, setHoy] = useState<DatosHoy | null>(null);
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [agregando, setAgregando] = useState(false);
  const [cerrando, setCerrando] = useState(false);
  const [nota, setNota] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {
    const [datosHoy, portafolio] = await Promise.all([
      api.get<DatosHoy>("/api/hoy"),
      api.get<{ proyectos: Proyecto[] }>("/api/portafolio"),
    ]);
    setHoy(datosHoy);
    setProyectos(portafolio.proyectos.filter((p) => p.estado === "activo"));
  }, []);

  useEffect(() => {
    cargar().catch((e) => setError(String(e.message ?? e)));
  }, [cargar]);

  if (error) return <Aviso error={error} recargar={() => { setError(""); cargar().catch((e) => setError(String(e))); }} />;
  if (!hoy) return <p className="text-sm text-[var(--tinta-suave)]">Cargando…</p>;

  const hechas = hoy.tareas.filter((t) => t.estado === "hecha").length;

  async function alternar(id: string, estado: string) {
    await api.patch(`/api/tareas/${id}`, { estado: estado === "hecha" ? "pendiente" : "hecha" });
    await cargar();
  }

  async function quitar(id: string) {
    if (!hoy) return;
    await api.put("/api/hoy", { tarea_ids: hoy.tareas.map((t) => t.id).filter((x) => x !== id) });
    await cargar();
  }

  async function agregar(id: string) {
    if (!hoy) return;
    // El error (p. ej. el límite de 6) llega por el toast global; la vista no se destruye.
    await api.put("/api/hoy", { tarea_ids: [...hoy.tareas.map((t) => t.id), id] }).catch(() => {});
    await cargar();
  }

  async function mover(i: number, delta: number) {
    if (!hoy) return;
    const ids = hoy.tareas.map((t) => t.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    await api.put("/api/hoy", { tarea_ids: ids });
    await cargar();
  }

  async function cerrarDia() {
    await api.post("/api/hoy/cerrar", { nota });
    setCerrando(false);
    setNota("");
    await cargar();
  }

  // Móvil primero (380 px): legible en 5 s, objetivos táctiles ≥ 44 px.
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px] lg:gap-6">
      {/* ---------- Plan del día ---------- */}
      <section>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">
            Hoy{" "}
            <span className="text-base font-semibold text-[var(--tinta-2)]">
              {hechas}/{hoy.tareas.length}
            </span>
            <span className="hidden text-sm font-normal text-[var(--tinta-suave)] sm:inline">
              {" "}· método Ivy Lee (máx. 6)
            </span>
          </h1>
          {!hoy.cerrado && (
            <button
              onClick={() => setCerrando(true)}
              className="min-h-11 rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-4 text-sm font-semibold hover:bg-black/5"
            >
              Cerrar el día
            </button>
          )}
        </div>

        {hoy.cerrado && (
          <div className="tarjeta mb-3 border-l-4 px-4 py-3 text-sm" style={{ borderLeftColor: "var(--ok)" }}>
            ✅ Día cerrado. {hoy.nota_cierre && <em>“{hoy.nota_cierre}”</em>}{" "}
            <span className="text-[var(--tinta-suave)]">Lo pendiente entra a la sugerencia de mañana.</span>
          </div>
        )}

        <ol className="space-y-2">
          {hoy.tareas.map((t, i) => {
            const hecha = t.estado === "hecha";
            return (
              <li key={t.id} className="tarjeta flex items-stretch gap-1 pr-1">
                {/* Toda la zona izquierda marca/desmarca: blanco táctil grande */}
                <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 py-3 pl-3">
                  <span className="w-5 shrink-0 text-center text-lg font-bold text-[var(--tinta-suave)]">{i + 1}</span>
                  <input
                    type="checkbox"
                    checked={hecha}
                    onChange={() => alternar(t.id, t.estado)}
                    className="h-7 w-7 shrink-0 accent-[var(--ok)]"
                    aria-label={`Completar ${t.titulo}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className={`block text-base leading-snug font-medium ${hecha ? "text-[var(--tinta-suave)] line-through" : ""}`}>
                      {t.es_hito && "◆ "}
                      {t.rutina_id && <span title="Rutina">↻ </span>}
                      {t.titulo}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5">
                      <ChipProyecto nombre={t.proyecto_nombre} color={t.proyecto_color} />
                      <EtiquetaCuadrante cuadrante={t.cuadrante} />
                      {t.fecha_fin !== hoy.fecha && (
                        <span className="text-xs text-[var(--tinta-suave)]">vence {fechaCorta(t.fecha_fin)}</span>
                      )}
                    </span>
                  </span>
                </label>
                {!hoy.cerrado && (
                  <div className="flex shrink-0 items-center">
                    {hoy.tareas.length > 1 && (
                      <div className="flex flex-col">
                        <button
                          onClick={() => mover(i, -1)}
                          disabled={i === 0}
                          className="h-9 w-9 text-[var(--tinta-suave)] hover:text-[var(--tinta)] disabled:opacity-20"
                          aria-label={`Subir ${t.titulo}`}
                        >
                          ▲
                        </button>
                        <button
                          onClick={() => mover(i, 1)}
                          disabled={i === hoy.tareas.length - 1}
                          className="h-9 w-9 text-[var(--tinta-suave)] hover:text-[var(--tinta)] disabled:opacity-20"
                          aria-label={`Bajar ${t.titulo}`}
                        >
                          ▼
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => quitar(t.id)}
                      title="Quitar del plan de hoy"
                      aria-label={`Quitar ${t.titulo} del plan`}
                      className="h-11 w-9 text-lg text-[var(--tinta-suave)] hover:text-[var(--critico)]"
                    >
                      ✕
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ol>

        {hoy.tareas.length === 0 && (
          <p className="tarjeta px-4 py-6 text-center text-sm text-[var(--tinta-suave)]">
            Sin plan para hoy. Agrega tareas o crea proyectos en el portafolio.
          </p>
        )}

        {/* Agregar desde candidatas */}
        {!hoy.cerrado && hoy.tareas.length < 6 && (
          <div className="mt-3">
            <button
              onClick={() => setAgregando(!agregando)}
              className="min-h-11 text-base font-semibold text-[var(--acento)] hover:underline"
            >
              {agregando ? "Ocultar candidatas" : `+ Agregar tarea (${6 - hoy.tareas.length} espacios)`}
            </button>
            {agregando && (
              <ul className="mt-1 space-y-1">
                {hoy.candidatas.slice(0, 10).map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => agregar(t.id)}
                      className="flex min-h-12 w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-black/5"
                      aria-label={`Agregar ${t.titulo}`}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--tinta)] text-lg font-bold text-white">
                        +
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium">{t.titulo}</span>
                        <span className="mt-0.5 flex flex-wrap gap-1.5">
                          <ChipProyecto nombre={t.proyecto_nombre} color={t.proyecto_color} />
                          <EtiquetaCuadrante cuadrante={t.cuadrante} />
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Cierre del día */}
        {cerrando && (
          <div className="tarjeta mt-4 space-y-3 p-4">
            <label className="block text-sm font-medium" htmlFor="nota-cierre">
              Nota de cierre (1 línea): ¿qué aprendiste hoy?
            </label>
            <input
              id="nota-cierre"
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              className="w-full rounded-lg border border-[var(--borde)] px-3 py-3 text-base"
              placeholder="Ej. la demo convence más que la presentación"
            />
            <div className="flex gap-2">
              <button onClick={cerrarDia} className="min-h-11 flex-1 rounded-lg bg-[var(--tinta)] px-4 text-base font-semibold text-white sm:flex-none">
                Cerrar día
              </button>
              <button onClick={() => setCerrando(false)} className="min-h-11 px-4 text-base text-[var(--tinta-2)]">
                Cancelar
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ---------- Semáforos y retos ---------- */}
      <aside className="space-y-5">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-[var(--tinta-2)]">Portafolio</h2>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
            {proyectos.map((p) => (
              <Link key={p.id} to={`/proyecto/${p.id}`} className="tarjeta block min-w-0 px-3 py-2.5 hover:bg-black/[.02] lg:px-4 lg:py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: p.color }} />
                    <span className="truncate">{p.nombre}</span>
                  </span>
                  {p.kpis && <Semaforo salud={p.kpis.salud} compacto />}
                </div>
                {p.kpis && (
                  <>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/10">
                      <div className="h-full rounded-full" style={{ width: `${p.kpis.avance_pct}%`, background: p.color }} />
                    </div>
                    <div className="mt-1.5 flex justify-between gap-1 text-xs text-[var(--tinta-suave)]">
                      <span>{p.kpis.avance_pct}%</span>
                      {p.kpis.proximo_hito && <span className="truncate">◆ {fechaCorta(p.kpis.proximo_hito.fecha)}</span>}
                    </div>
                  </>
                )}
              </Link>
            ))}
          </div>
        </section>

        {hoy.retos_arden.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold text-[var(--tinta-2)]">🔥 Retos que arden</h2>
            <ul className="space-y-2">
              {hoy.retos_arden.map((r) => (
                <li key={r.id} className="tarjeta border-l-4 px-3 py-2" style={{ borderLeftColor: (r.puntaje ?? 0) >= 16 ? "var(--critico)" : "var(--alerta)" }}>
                  <div className="text-sm font-medium">{r.titulo}</div>
                  <div className="mt-0.5 text-xs text-[var(--tinta-suave)]">
                    {r.proyecto_nombre} · impacto {r.impacto} × prob. {r.probabilidad} = {r.puntaje}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>
    </div>
  );
}

function Aviso({ error, recargar }: { error: string; recargar: () => void }) {
  return (
    <div className="tarjeta mx-auto max-w-md p-6 text-center">
      <p className="text-sm text-[var(--critico)]">{error}</p>
      <button onClick={recargar} className="mt-3 rounded-lg bg-[var(--tinta)] px-3 py-1.5 text-sm text-white">
        Reintentar
      </button>
    </div>
  );
}
