import { useState } from "react";
import { api } from "../api";
import type { Canal } from "../tipos";
import { CANALES, enDias, RESULTADOS_RAPIDOS } from "./captacion";

// Registrar interacción en 2 toques (Fase 1): abrir + tocar el resultado.
// Canal y próxima acción vienen preseleccionados (llamada, seguimiento en 3 días);
// cambiarlos o escribir una nota es opcional.

const PROXIMAS = [
  { texto: "Mañana", dias: 1 },
  { texto: "En 3 días", dias: 3 },
  { texto: "En 1 semana", dias: 7 },
  { texto: "Sin acción", dias: null },
] as const;

export default function RegistrarInteraccion({
  prospectoId,
  empresa,
  onListo,
  onCerrar,
}: {
  prospectoId: string;
  empresa: string;
  onListo: () => void;
  onCerrar: () => void;
}) {
  const [canal, setCanal] = useState<Canal>("llamada");
  const [dias, setDias] = useState<number | null>(3);
  const [accion, setAccion] = useState("Seguimiento");
  const [nota, setNota] = useState("");
  const [otro, setOtro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function guardar(resultado: string) {
    if (!resultado.trim() || enviando) return;
    setEnviando(true);
    try {
      await api.post(`/api/captacion/prospectos/${prospectoId}/interacciones`, {
        canal,
        resultado: resultado.trim(),
        nota,
        proxima_accion: dias === null ? "" : accion,
        fecha_proxima_accion: dias === null ? null : enDias(dias),
      });
      onListo();
    } catch {
      setEnviando(false); // el toast global ya avisó
    }
  }

  const chip = (activo: boolean) =>
    `min-h-10 rounded-lg px-3 text-sm font-medium ${
      activo ? "bg-[var(--tinta)] text-white" : "border border-[var(--borde)] text-[var(--tinta-2)]"
    }`;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center" onClick={onCerrar}>
      <div
        className="tarjeta max-h-[92vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-b-none p-4 sm:rounded-b-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Registrar interacción con ${empresa}`}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs text-[var(--tinta-suave)]">Registrar interacción</p>
            <h2 className="text-lg font-bold">{empresa}</h2>
          </div>
          <button onClick={onCerrar} className="h-10 w-10 text-lg text-[var(--tinta-suave)]" aria-label="Cerrar">
            ✕
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Canal">
          {CANALES.map((c) => (
            <button key={c.clave} onClick={() => setCanal(c.clave)} className={chip(canal === c.clave)} aria-pressed={canal === c.clave}>
              {c.icono} {c.texto}
            </button>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-semibold">Próxima acción</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Próxima acción">
            {PROXIMAS.map((p) => (
              <button key={p.texto} onClick={() => setDias(p.dias)} className={chip(dias === p.dias)} aria-pressed={dias === p.dias}>
                {p.texto}
              </button>
            ))}
          </div>
          {dias !== null && (
            <input
              value={accion}
              onChange={(e) => setAccion(e.target.value)}
              className="w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-base"
              aria-label="Qué sigue"
              placeholder="Qué sigue (ej. enviar demo)"
            />
          )}
          <input
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            className="w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-base"
            placeholder="Nota (opcional)"
            aria-label="Nota"
          />
        </div>

        <div>
          <p className="mb-2 text-sm font-semibold">¿Qué pasó? (toca para guardar)</p>
          <div className="grid grid-cols-2 gap-2">
            {RESULTADOS_RAPIDOS.map((r) => (
              <button
                key={r}
                disabled={enviando}
                onClick={() => guardar(r)}
                className="min-h-12 rounded-lg bg-[var(--acento)] px-3 text-sm font-semibold text-white disabled:opacity-40"
              >
                {r}
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={otro}
              onChange={(e) => setOtro(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && guardar(otro)}
              className="min-w-0 flex-1 rounded-lg border border-[var(--borde)] px-3 py-2 text-base"
              placeholder="Otro resultado…"
              aria-label="Otro resultado"
            />
            <button
              disabled={!otro.trim() || enviando}
              onClick={() => guardar(otro)}
              className="min-h-11 rounded-lg bg-[var(--tinta)] px-4 text-sm font-semibold text-white disabled:opacity-40"
            >
              Guardar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
