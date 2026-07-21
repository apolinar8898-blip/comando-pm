import { useState } from "react";
import { api } from "../api";
import type { DetalleProyecto, Reto } from "../tipos";

// Retos (CLAUDE.md §4.3.5): matriz impacto×probabilidad 5×5 (mapa de calor)
// + lista con plan de respuesta. Un reto materializado puede abrir su RCA.

const TIPOS = [
  ["riesgo", "Riesgo"],
  ["bloqueo", "Bloqueo"],
  ["decision_pendiente", "Decisión pendiente"],
] as const;

const ESTADOS_RETO = ["abierto", "mitigado", "materializado", "cerrado"] as const;

// Zonas de severidad alineadas con la regla de salud del dominio:
// puntaje ≥16 = crítico (rojo), ≥9 = alerta (amarillo), resto = ok.
function colorZona(puntaje: number): string {
  if (puntaje >= 16) return "var(--critico)";
  if (puntaje >= 9) return "var(--alerta)";
  return "var(--ok)";
}

export default function Retos({ detalle, recargar, irADocs }: {
  detalle: DetalleProyecto;
  recargar: () => Promise<void>;
  irADocs: () => void;
}) {
  const [creando, setCreando] = useState(false);
  const [forma, setForma] = useState({ titulo: "", tipo: "riesgo", impacto: 3, probabilidad: 3, plan_de_respuesta: "" });
  const abiertos = detalle.retos.filter((r) => r.estado === "abierto");

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    await api.post(`/api/proyectos/${detalle.proyecto.id}/retos`, forma);
    setForma({ ...forma, titulo: "", plan_de_respuesta: "" });
    setCreando(false);
    await recargar();
  }

  async function cambiarEstado(rid: string, estado: string) {
    await api.patch(`/api/retos/${rid}`, { estado });
    await recargar();
  }

  async function hacerRca(reto: Reto) {
    await api.post("/api/documentos", {
      proyecto_id: detalle.proyecto.id,
      tipo: "rca",
      contenido: {
        que_paso: `Se materializó el reto: ${reto.titulo}`,
        reto_origen: reto.id,
        porques: [],
        acciones: [],
      },
    });
    irADocs();
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        {/* Mapa de calor 5×5 */}
        <div className="tarjeta p-4">
          <h3 className="mb-2 text-sm font-semibold">Matriz impacto × probabilidad</h3>
          <p className="mb-3 text-[10px] text-[var(--tinta-suave)]">Solo retos abiertos. El número es cuántos caen en la celda.</p>
          <div className="flex gap-1">
            <div className="flex flex-col items-center justify-center">
              <span className="-rotate-90 whitespace-nowrap text-[9px] uppercase tracking-wide text-[var(--tinta-suave)]">Probabilidad ↑</span>
            </div>
            <div className="flex-1">
              <div className="grid grid-cols-5 gap-1">
                {[5, 4, 3, 2, 1].map((prob) =>
                  [1, 2, 3, 4, 5].map((imp) => {
                    const enCelda = abiertos.filter((r) => r.impacto === imp && r.probabilidad === prob);
                    const color = colorZona(imp * prob);
                    return (
                      <div
                        key={`${prob}-${imp}`}
                        title={enCelda.map((r) => r.titulo).join("\n") || `impacto ${imp} × probabilidad ${prob} = ${imp * prob}`}
                        className="flex aspect-square items-center justify-center rounded-md text-sm font-bold"
                        style={{
                          background: color,
                          opacity: enCelda.length > 0 ? 0.95 : 0.18,
                          color: enCelda.length > 0 ? "#fff" : "transparent",
                        }}
                      >
                        {enCelda.length || "·"}
                      </div>
                    );
                  }),
                )}
              </div>
              <p className="mt-1 text-center text-[9px] uppercase tracking-wide text-[var(--tinta-suave)]">Impacto →</p>
            </div>
          </div>
          <div className="mt-2 flex justify-center gap-3 text-[9px] text-[var(--tinta-2)]">
            <span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: "var(--ok)" }} />aceptable (&lt;9)</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: "var(--alerta)" }} />vigilar (9-15)</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: "var(--critico)" }} />crítico (≥16)</span>
          </div>
        </div>

        {/* Lista + alta */}
        <div className="tarjeta p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Retos del proyecto</h3>
            <button onClick={() => setCreando(!creando)} className="rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs font-medium hover:bg-black/5">
              {creando ? "Cancelar" : "＋ Nuevo reto"}
            </button>
          </div>

          {creando && (
            <form onSubmit={crear} className="mb-4 grid gap-3 rounded-lg border border-dashed border-[var(--grid)] p-3 sm:grid-cols-2">
              <label className="text-xs text-[var(--tinta-2)] sm:col-span-2">
                ¿Qué puede salir mal / qué está estorbando?
                <input required value={forma.titulo} onChange={(e) => setForma({ ...forma, titulo: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm" />
              </label>
              <label className="text-xs text-[var(--tinta-2)]">
                Tipo
                <select value={forma.tipo} onChange={(e) => setForma({ ...forma, tipo: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-2 py-2 text-sm">
                  {TIPOS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {(["impacto", "probabilidad"] as const).map((campo) => (
                  <label key={campo} className="text-xs capitalize text-[var(--tinta-2)]">
                    {campo} (1-5)
                    <select value={forma[campo]} onChange={(e) => setForma({ ...forma, [campo]: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-2 py-2 text-sm">
                      {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              <label className="text-xs text-[var(--tinta-2)] sm:col-span-2">
                Plan de respuesta
                <input value={forma.plan_de_respuesta} onChange={(e) => setForma({ ...forma, plan_de_respuesta: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm" placeholder="¿Qué se hará si pasa / para que no pase?" />
              </label>
              <button type="submit" className="rounded-lg bg-[var(--tinta)] px-4 py-2 text-sm font-medium text-white sm:col-span-2">Guardar reto</button>
            </form>
          )}

          {detalle.retos.length === 0 && !creando && (
            <p className="text-xs text-[var(--tinta-suave)]">Sin retos registrados. Registrar riesgos a tiempo es más barato que apagarlos.</p>
          )}

          <ul className="space-y-3">
            {[...detalle.retos]
              .sort((a, b) => (a.estado === "abierto" ? -1 : 1) - (b.estado === "abierto" ? -1 : 1) || b.impacto * b.probabilidad - a.impacto * a.probabilidad)
              .map((r) => (
                <li key={r.id} className="rounded-lg border border-[var(--grid)] p-3" style={{ borderLeftWidth: 4, borderLeftColor: r.estado === "abierto" ? colorZona(r.impacto * r.probabilidad) : "var(--eje)" }}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className={`text-xs font-medium ${r.estado === "cerrado" ? "text-[var(--tinta-suave)] line-through" : ""}`}>{r.titulo}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-[var(--tinta-suave)]">{r.impacto}×{r.probabilidad} = <strong>{r.impacto * r.probabilidad}</strong></span>
                      <select value={r.estado} onChange={(e) => cambiarEstado(r.id, e.target.value)} className="rounded border border-[var(--borde)] px-1 py-0.5 text-[10px]" aria-label={`Estado de ${r.titulo}`}>
                        {ESTADOS_RETO.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                  </div>
                  <p className="mt-1 text-[10px] text-[var(--tinta-suave)]">
                    {TIPOS.find(([v]) => v === r.tipo)?.[1] ?? r.tipo}
                    {r.plan_de_respuesta && ` · plan: ${r.plan_de_respuesta}`}
                  </p>
                  {r.estado === "materializado" && (
                    <button onClick={() => hacerRca(r)} className="mt-2 rounded-lg bg-[var(--critico)] px-2.5 py-1 text-[11px] font-semibold text-white">
                      Hacer análisis causa raíz →
                    </button>
                  )}
                </li>
              ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
