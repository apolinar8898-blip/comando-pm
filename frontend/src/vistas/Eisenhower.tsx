import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Tarea } from "../tipos";
import { ChipProyecto, fechaCorta } from "../componentes/Chips";

// Matriz de Eisenhower 2×2 con drag & drop (CLAUDE.md §4.3.4).
// Arrastrar una tarea a un cuadrante fija sus flags: el cuadrante nunca se
// guarda, se deriva de (importante, urgente_manual) en el dominio.

const CUADRANTES = [
  { n: 1, titulo: "I · Hacer ya", sub: "Urgente e importante", borde: "var(--critico)", flags: { importante: true, urgente_manual: true } },
  { n: 2, titulo: "II · Planear", sub: "Importante, no urgente", borde: "var(--acento)", flags: { importante: true, urgente_manual: false } },
  { n: 3, titulo: "III · Rápido o delegar", sub: "Urgente, no importante", borde: "var(--alerta)", flags: { importante: false, urgente_manual: true } },
  { n: 4, titulo: "IV · Cuestionar", sub: "Ni urgente ni importante", borde: "var(--eje)", flags: { importante: false, urgente_manual: false } },
] as const;

export default function Eisenhower({ proyectoId }: { proyectoId?: string }) {
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [sobre, setSobre] = useState<number | null>(null);
  const [seleccion, setSeleccion] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const r = await api.get<{ tareas: Tarea[] }>(
      `/api/tareas${proyectoId ? `?proyecto_id=${proyectoId}` : ""}`,
    );
    setTareas(r.tareas.filter((t) => (t.estado === "pendiente" || t.estado === "en_curso") && !t.expirada));
  }, [proyectoId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function mover(id: string, cuadrante: (typeof CUADRANTES)[number]) {
    setSeleccion(null);
    const tarea = tareas.find((t) => t.id === id);
    if (!tarea || tarea.cuadrante === cuadrante.n) return;
    await api.patch(`/api/tareas/${id}`, cuadrante.flags);
    await cargar();
  }

  async function soltar(e: React.DragEvent, cuadrante: (typeof CUADRANTES)[number]) {
    e.preventDefault();
    setSobre(null);
    await mover(e.dataTransfer.getData("texto/tarea"), cuadrante);
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--tinta-suave)]">
        Arrastra una tarea a otro cuadrante para repriorizarla (fija urgencia/importancia
        manualmente). Sin flag manual, la urgencia es automática: vence en ≤ 2 días.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {CUADRANTES.map((c) => {
          const propias = tareas.filter((t) => t.cuadrante === c.n);
          return (
            <section
              key={c.n}
              onDragOver={(e) => {
                e.preventDefault();
                setSobre(c.n);
              }}
              onDragLeave={() => setSobre(null)}
              onDrop={(e) => soltar(e, c)}
              className={`tarjeta min-h-40 border-t-4 p-3 transition-colors ${sobre === c.n ? "bg-black/[.04]" : ""}`}
              style={{ borderTopColor: c.borde }}
            >
              <header className="mb-2">
                <h2 className="text-sm font-bold">{c.titulo}</h2>
                <p className="text-[10px] uppercase tracking-wide text-[var(--tinta-suave)]">
                  {c.sub} · {propias.length}
                </p>
              </header>
              <ul className="space-y-1.5">
                {propias.map((t) => (
                  <li
                    key={t.id}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("texto/tarea", t.id)}
                    onClick={() => setSeleccion(seleccion === t.id ? null : t.id)}
                    className="cursor-grab rounded-lg border border-[var(--borde)] bg-[var(--plano)] px-3 py-2 active:cursor-grabbing"
                  >
                    <p className="text-xs font-medium">
                      {t.es_hito && "◆ "}
                      {t.titulo}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      {!proyectoId && <ChipProyecto nombre={t.proyecto_nombre} color={t.proyecto_color} />}
                      <span className="text-[10px] text-[var(--tinta-suave)]">vence {fechaCorta(t.fecha_fin)}</span>
                      {t.estado === "en_curso" && (
                        <span className="rounded bg-black/10 px-1 text-[9px] font-semibold">EN CURSO</span>
                      )}
                    </div>
                    {seleccion === t.id && (
                      <div className="mt-2 flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <span className="text-[10px] text-[var(--tinta-suave)]">Mover a:</span>
                        {CUADRANTES.filter((o) => o.n !== t.cuadrante).map((o) => (
                          <button
                            key={o.n}
                            onClick={() => mover(t.id, o)}
                            title={o.titulo}
                            className="rounded border border-[var(--borde)] bg-[var(--superficie)] px-2 py-0.5 text-[10px] font-bold hover:bg-black/5"
                          >
                            {["I", "II", "III", "IV"][o.n - 1]}
                          </button>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
                {propias.length === 0 && (
                  <li className="rounded-lg border border-dashed border-[var(--grid)] px-3 py-3 text-center text-[10px] text-[var(--tinta-suave)]">
                    Suelta tareas aquí
                  </li>
                )}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
