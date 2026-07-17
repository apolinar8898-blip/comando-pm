// Piezas chicas compartidas: chip de proyecto y etiqueta de cuadrante Eisenhower.

export function ChipProyecto({ nombre, color }: { nombre: string; color: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--borde)] px-2 py-0.5 text-[11px] text-[var(--tinta-2)]">
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: color }}
        aria-hidden
      />
      {nombre}
    </span>
  );
}

const CUADRANTES: Record<number, { texto: string; titulo: string }> = {
  1: { texto: "I · Hacer ya", titulo: "Urgente e importante" },
  2: { texto: "II · Planear", titulo: "Importante, no urgente" },
  3: { texto: "III · Rápido", titulo: "Urgente, no importante" },
  4: { texto: "IV · Revisar", titulo: "Ni urgente ni importante" },
};

export function EtiquetaCuadrante({ cuadrante }: { cuadrante: number }) {
  const c = CUADRANTES[cuadrante] ?? CUADRANTES[4];
  return (
    <span
      title={c.titulo}
      className="rounded bg-black/5 px-1.5 py-0.5 text-[10px] font-medium text-[var(--tinta-suave)]"
    >
      {c.texto}
    </span>
  );
}

export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${d} ${meses[m - 1]} ${a !== new Date().getFullYear() ? a : ""}`.trim();
}
