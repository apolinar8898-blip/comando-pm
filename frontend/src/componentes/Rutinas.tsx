import { useState } from "react";
import { api } from "../api";
import type { Rutina } from "../tipos";
import { fechaCorta } from "./Chips";

// Rutinas del proyecto: trabajo recurrente (entreno, prospección, post diario).
// Cada día que toca, el backend crea la tarea real del día (↻ en Hoy).
// Nada se borra: una rutina que ya no aplica se pausa.

const DIAS = ["L", "M", "X", "J", "V", "S", "D"];
const DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

function SelectorDias({ dias, onCambio }: { dias: number[]; onCambio: (d: number[]) => void }) {
  return (
    <div className="flex gap-1">
      {DIAS.map((letra, i) => {
        const activo = dias.includes(i);
        return (
          <button
            key={i}
            type="button"
            onClick={() => onCambio(activo ? dias.filter((d) => d !== i) : [...dias, i].sort())}
            aria-pressed={activo}
            aria-label={DIAS_LARGOS[i]}
            className={`h-9 w-9 rounded-lg text-sm font-semibold ${
              activo ? "bg-[var(--tinta)] text-white" : "border border-[var(--borde)] text-[var(--tinta-2)]"
            }`}
          >
            {letra}
          </button>
        );
      })}
    </div>
  );
}

export default function Rutinas({
  proyectoId,
  rutinas,
  onCambio,
}: {
  proyectoId: string;
  rutinas: Rutina[];
  onCambio: () => void;
}) {
  const [titulo, setTitulo] = useState("");
  const [dias, setDias] = useState<number[]>([0, 1, 2, 3, 4]);
  const [horas, setHoras] = useState(1);

  async function editar(r: Rutina, cambios: Partial<Rutina>) {
    await api.patch(`/api/rutinas/${r.id}`, cambios).catch(() => {});
    onCambio();
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    await api
      .post(`/api/proyectos/${proyectoId}/rutinas`, { titulo, dias_semana: dias, esfuerzo_estimado_h: horas })
      .then(() => setTitulo(""))
      .catch(() => {});
    onCambio();
  }

  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {rutinas.length === 0 && (
          <li className="text-sm text-[var(--tinta-suave)]">Sin rutinas. Agrega abajo el trabajo que se repite.</li>
        )}
        {rutinas.map((r) => (
          <li key={r.id} className={`tarjeta space-y-2 p-3 ${r.activa ? "" : "opacity-50"}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium">↻ {r.titulo}</p>
                <p className="text-xs text-[var(--tinta-suave)]">
                  {r.esfuerzo_estimado_h} h · desde {fechaCorta(r.desde)}
                  {r.hasta && ` hasta ${fechaCorta(r.hasta)}`}
                </p>
              </div>
              <button
                onClick={() => editar(r, { activa: !r.activa })}
                className="min-h-9 shrink-0 rounded-lg border border-[var(--borde)] px-3 text-xs font-medium hover:bg-black/5"
              >
                {r.activa ? "Pausar" : "Reactivar"}
              </button>
            </div>
            <SelectorDias
              dias={r.dias_semana}
              onCambio={(d) => d.length > 0 && editar(r, { dias_semana: d })}
            />
          </li>
        ))}
      </ul>

      <form onSubmit={crear} className="tarjeta space-y-3 p-3">
        <h3 className="text-sm font-semibold">Nueva rutina</h3>
        <input
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          placeholder="Ej. Llamar a 5 prospectos de CANACINTRA"
          className="w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-base"
        />
        <SelectorDias dias={dias} onCambio={setDias} />
        <label className="flex items-center gap-2 text-sm">
          Horas por sesión
          <input
            type="number"
            min={0}
            step={0.25}
            value={horas}
            onChange={(e) => setHoras(Number(e.target.value))}
            className="w-20 rounded-lg border border-[var(--borde)] px-2 py-1.5 text-base"
          />
        </label>
        <button
          disabled={!titulo.trim() || dias.length === 0}
          className="min-h-11 rounded-lg bg-[var(--tinta)] px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          Agregar rutina
        </button>
      </form>
    </div>
  );
}
