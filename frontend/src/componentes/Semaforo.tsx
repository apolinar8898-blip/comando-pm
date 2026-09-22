import type { Salud } from "../tipos";

// Semáforo calculado por el backend. Nunca color solo: siempre icono + texto.
const ESTILOS: Record<Salud, { color: string; icono: string; texto: string }> = {
  verde: { color: "var(--ok)", icono: "●", texto: "Al día" },
  amarillo: { color: "var(--alerta)", icono: "▲", texto: "En riesgo" },
  rojo: { color: "var(--critico)", icono: "■", texto: "Crítico" },
};

// compacto: en celular solo el icono (el texto queda para lectores de pantalla).
export default function Semaforo({ salud, compacto = false }: { salud: Salud; compacto?: boolean }) {
  const e = ESTILOS[salud];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold"
      style={{ color: e.color }}
    >
      <span aria-hidden>{e.icono}</span>
      <span className={compacto ? "sr-only lg:not-sr-only lg:text-[var(--tinta-2)]" : "text-[var(--tinta-2)]"}>{e.texto}</span>
    </span>
  );
}
