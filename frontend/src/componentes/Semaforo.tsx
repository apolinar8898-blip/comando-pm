import type { Salud } from "../tipos";

// Semáforo calculado por el backend. Nunca color solo: siempre icono + texto.
const ESTILOS: Record<Salud, { color: string; icono: string; texto: string }> = {
  verde: { color: "var(--ok)", icono: "●", texto: "Al día" },
  amarillo: { color: "var(--alerta)", icono: "▲", texto: "En riesgo" },
  rojo: { color: "var(--critico)", icono: "■", texto: "Crítico" },
};

export default function Semaforo({ salud }: { salud: Salud }) {
  const e = ESTILOS[salud];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold"
      style={{ color: e.color }}
    >
      <span aria-hidden>{e.icono}</span>
      <span className="text-[var(--tinta-2)]">{e.texto}</span>
    </span>
  );
}
