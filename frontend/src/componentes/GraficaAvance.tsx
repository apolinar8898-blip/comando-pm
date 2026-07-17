import { useState } from "react";
import type { Snapshot } from "../tipos";
import { fechaCorta } from "./Chips";

// Línea de avance % vs tiempo (una serie: sin leyenda, el título la nombra).
// Se alimenta de los snapshots diarios de KPIs.

const ANCHO = 640;
const ALTO = 200;
const MARGEN = { arriba: 14, abajo: 24, izq: 34, der: 12 };

export default function GraficaAvance({ snapshots }: { snapshots: Snapshot[] }) {
  const [cerca, setCerca] = useState<number | null>(null);

  const plotW = ANCHO - MARGEN.izq - MARGEN.der;
  const plotH = ALTO - MARGEN.arriba - MARGEN.abajo;
  const n = snapshots.length;
  const px = (i: number) => MARGEN.izq + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const py = (v: number) => MARGEN.arriba + (1 - v / 100) * plotH;

  const linea = snapshots.map((s, i) => `${i ? "L" : "M"} ${px(i)} ${py(s.avance_pct)}`).join(" ");

  function alMover(e: React.MouseEvent<SVGSVGElement>) {
    if (!n) return;
    const caja = e.currentTarget.getBoundingClientRect();
    const xRel = ((e.clientX - caja.left) / caja.width) * ANCHO;
    let mejor = 0;
    for (let i = 1; i < n; i++) if (Math.abs(px(i) - xRel) < Math.abs(px(mejor) - xRel)) mejor = i;
    setCerca(mejor);
  }

  return (
    <div className="tarjeta p-4">
      <h3 className="mb-1 text-sm font-semibold">Avance del proyecto (%)</h3>
      {n === 0 ? (
        <p className="py-6 text-center text-xs text-[var(--tinta-suave)]">
          Sin datos aún: la gráfica se llena con la foto diaria de KPIs.
        </p>
      ) : (
        <svg
          viewBox={`0 0 ${ANCHO} ${ALTO}`}
          className="w-full"
          onMouseMove={alMover}
          onMouseLeave={() => setCerca(null)}
        >
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={MARGEN.izq} y1={py(v)} x2={ANCHO - MARGEN.der} y2={py(v)} stroke="var(--grid)" />
              <text x={MARGEN.izq - 6} y={py(v) + 3} fontSize={9} textAnchor="end" fill="var(--tinta-suave)">
                {v}
              </text>
            </g>
          ))}
          <path d={linea} fill="none" stroke="var(--acento)" strokeWidth={2} />
          {snapshots.map((s, i) => (
            <circle
              key={s.fecha}
              cx={px(i)}
              cy={py(s.avance_pct)}
              r={cerca === i ? 5 : 3.5}
              fill="var(--acento)"
              stroke="var(--superficie)"
              strokeWidth={2}
            />
          ))}
          {cerca !== null && (
            <g>
              <line
                x1={px(cerca)}
                y1={MARGEN.arriba}
                x2={px(cerca)}
                y2={ALTO - MARGEN.abajo}
                stroke="var(--eje)"
                strokeDasharray="3 3"
              />
              <g
                transform={`translate(${Math.min(px(cerca) + 8, ANCHO - 150)}, ${MARGEN.arriba + 4})`}
              >
                <rect width={140} height={38} rx={6} fill="var(--tinta)" opacity={0.92} />
                <text x={8} y={15} fontSize={10} fill="#fff" fontWeight={600}>
                  {fechaCorta(snapshots[cerca].fecha)}
                </text>
                <text x={8} y={29} fontSize={10} fill="#fff">
                  Avance {snapshots[cerca].avance_pct}% · SPI {snapshots[cerca].spi}
                </text>
              </g>
            </g>
          )}
          {/* Último valor con etiqueta directa */}
          <text
            x={px(n - 1)}
            y={py(snapshots[n - 1].avance_pct) - 9}
            fontSize={11}
            fontWeight={700}
            textAnchor="middle"
            fill="var(--tinta)"
          >
            {snapshots[n - 1].avance_pct}%
          </text>
        </svg>
      )}
    </div>
  );
}
