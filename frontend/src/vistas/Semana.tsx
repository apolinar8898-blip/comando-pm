import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Tarea } from "../tipos";
import { ChipProyecto } from "../componentes/Chips";

// Plan semanal (CLAUDE.md §4.3.3): tablero lunes-domingo. Arrastrar una tarea
// a otro día la reprograma conservando su duración (igual que el Gantt).

const DIA_MS = 86_400_000;
const aFecha = (iso: string) => new Date(iso + "T00:00:00");
const aIso = (d: Date) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return z.toISOString().slice(0, 10);
};

function lunesDe(fecha: Date): Date {
  const d = new Date(fecha.toDateString());
  const dia = d.getDay(); // 0 = domingo
  d.setDate(d.getDate() - (dia === 0 ? 6 : dia - 1));
  return d;
}

const NOMBRES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export default function Semana({ proyectoId }: { proyectoId?: string }) {
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [lunes, setLunes] = useState<Date>(() => lunesDe(new Date()));
  const [sobre, setSobre] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const r = await api.get<{ tareas: Tarea[] }>(
      `/api/tareas${proyectoId ? `?proyecto_id=${proyectoId}` : ""}`,
    );
    setTareas(r.tareas);
  }, [proyectoId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const hoyIso = aIso(new Date());
  const dias = Array.from({ length: 7 }, (_, i) => {
    const f = new Date(lunes.getTime() + i * DIA_MS);
    return { iso: aIso(f), nombre: NOMBRES[i], numero: f.getDate() };
  });
  const vencidas = tareas.filter((t) => t.estado !== "hecha" && t.fecha_fin < hoyIso);

  async function reprogramar(id: string, destinoIso: string) {
    setSeleccion(null);
    const t = tareas.find((x) => x.id === id);
    if (!t || t.fecha_fin === destinoIso) return;
    const delta = Math.round((aFecha(destinoIso).getTime() - aFecha(t.fecha_fin).getTime()) / DIA_MS);
    const inicio = aFecha(t.fecha_inicio);
    inicio.setDate(inicio.getDate() + delta);
    await api.patch(`/api/tareas/${t.id}`, { fecha_inicio: aIso(inicio), fecha_fin: destinoIso });
    await cargar();
  }

  async function soltarEnDia(e: React.DragEvent, destinoIso: string) {
    e.preventDefault();
    setSobre(null);
    await reprogramar(e.dataTransfer.getData("texto/tarea"), destinoIso);
  }

  function mover(semanas: number) {
    const d = new Date(lunes);
    d.setDate(d.getDate() + semanas * 7);
    setLunes(d);
  }

  const rango = `${dias[0].numero} — ${dias[6].numero} · ${lunes.toLocaleDateString("es-MX", { month: "long", year: "numeric" })}`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[var(--tinta-suave)]">
          Las tareas aparecen el día que vencen. Arrastra a otro día para reprogramar
          (conserva la duración).
        </p>
        <div className="flex items-center gap-1 text-sm">
          <button onClick={() => mover(-1)} className="rounded px-2 py-0.5 hover:bg-black/5" aria-label="Semana anterior">‹</button>
          <button onClick={() => setLunes(lunesDe(new Date()))} className="rounded px-2 py-0.5 text-xs font-medium hover:bg-black/5">
            Esta semana
          </button>
          <button onClick={() => mover(1)} className="rounded px-2 py-0.5 hover:bg-black/5" aria-label="Semana siguiente">›</button>
          <span className="ml-2 text-xs font-semibold capitalize">{rango}</span>
        </div>
      </div>

      {vencidas.length > 0 && (
        <div className="tarjeta border-l-4 p-3" style={{ borderLeftColor: "var(--critico)" }}>
          <h3 className="mb-1.5 text-xs font-bold text-[var(--critico)]">
            Vencidas sin reprogramar ({vencidas.length}) — arrástralas a un día
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {vencidas.map((t) => (
              <span
                key={t.id}
                draggable
                onDragStart={(e) => e.dataTransfer.setData("texto/tarea", t.id)}
                onClick={() => setSeleccion(seleccion === t.id ? null : t.id)}
                className="inline-flex cursor-grab items-center gap-1.5 rounded-full border border-[var(--borde)] bg-[var(--plano)] px-2.5 py-1 text-[11px] active:cursor-grabbing"
              >
                <span className="h-2 w-2 rounded-full" style={{ background: t.proyecto_color }} />
                {t.es_hito && "◆ "}
                {t.titulo}
                {seleccion === t.id && (
                  <input
                    type="date"
                    defaultValue={t.fecha_fin}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => e.target.value && reprogramar(t.id, e.target.value)}
                    className="rounded border border-[var(--borde)] bg-[var(--superficie)] px-1 text-[10px]"
                    aria-label={`Reprogramar ${t.titulo}`}
                  />
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <div className="grid min-w-[840px] grid-cols-7 gap-2">
          {dias.map((d) => {
            const delDia = tareas.filter((t) => t.fecha_fin === d.iso);
            const esHoy = d.iso === hoyIso;
            return (
              <section
                key={d.iso}
                onDragOver={(e) => {
                  e.preventDefault();
                  setSobre(d.iso);
                }}
                onDragLeave={() => setSobre(null)}
                onDrop={(e) => soltarEnDia(e, d.iso)}
                className={`tarjeta min-h-44 p-2 transition-colors ${sobre === d.iso ? "bg-black/[.04]" : ""} ${esHoy ? "ring-2 ring-[var(--acento)]" : ""}`}
              >
                <header className={`mb-2 text-center text-[11px] font-bold ${esHoy ? "text-[var(--acento)]" : "text-[var(--tinta-2)]"}`}>
                  {d.nombre} {d.numero}
                  {esHoy && <span className="ml-1 font-normal">· hoy</span>}
                </header>
                <ul className="space-y-1.5">
                  {delDia.map((t) => (
                    <li
                      key={t.id}
                      draggable={t.estado !== "hecha"}
                      onDragStart={(e) => e.dataTransfer.setData("texto/tarea", t.id)}
                      onClick={() => t.estado !== "hecha" && setSeleccion(seleccion === t.id ? null : t.id)}
                      className={`rounded-md border border-[var(--borde)] px-2 py-1.5 text-[11px] ${
                        t.estado === "hecha"
                          ? "bg-transparent text-[var(--tinta-suave)] line-through"
                          : "cursor-grab bg-[var(--plano)] active:cursor-grabbing"
                      }`}
                      style={{ borderLeftWidth: 3, borderLeftColor: t.proyecto_color }}
                    >
                      {t.es_hito && "◆ "}
                      {t.titulo}
                      {!proyectoId && (
                        <div className="mt-1">
                          <ChipProyecto nombre={t.proyecto_nombre} color={t.proyecto_color} />
                        </div>
                      )}
                      {seleccion === t.id && (
                        <input
                          type="date"
                          defaultValue={t.fecha_fin}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => e.target.value && reprogramar(t.id, e.target.value)}
                          className="mt-1.5 w-full rounded border border-[var(--borde)] bg-[var(--superficie)] px-1 py-0.5 text-[10px]"
                          aria-label={`Reprogramar ${t.titulo}`}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
