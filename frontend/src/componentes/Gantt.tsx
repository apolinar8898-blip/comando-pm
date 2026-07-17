import { useMemo, useRef, useState } from "react";
import type { Tarea } from "../tipos";

// Gantt propio en SVG (decisión documentada en README: control total del
// drag, hitos y ruta crítica sin depender de librerías con API inestable).

const ALTO_FILA = 34;
const ZOOMS = { dia: 28, semana: 12, mes: 5 } as const;
type Zoom = keyof typeof ZOOMS;

const DIA_MS = 86_400_000;
const aFecha = (iso: string) => new Date(iso + "T00:00:00");
const aIso = (d: Date) => d.toISOString().slice(0, 10);
const dias = (a: Date, b: Date) => Math.round((b.getTime() - a.getTime()) / DIA_MS);

interface Props {
  tareas: Tarea[];
  rutaCritica: string[];
  onMover: (id: string, fechaInicio: string, fechaFin: string) => void;
}

export default function Gantt({ tareas, rutaCritica, onMover }: Props) {
  const [zoom, setZoom] = useState<Zoom>("semana");
  const [arrastre, setArrastre] = useState<{ id: string; x0: number; dx: number } | null>(null);
  const criticas = useMemo(() => new Set(rutaCritica), [rutaCritica]);
  const contenedor = useRef<HTMLDivElement>(null);

  const pxDia = ZOOMS[zoom];
  const hoy = new Date(new Date().toDateString());

  const { inicio, totalDias } = useMemo(() => {
    if (!tareas.length) return { inicio: hoy, totalDias: 30 };
    const min = tareas.reduce((m, t) => (t.fecha_inicio < m ? t.fecha_inicio : m), tareas[0].fecha_inicio);
    const max = tareas.reduce((m, t) => (t.fecha_fin > m ? t.fecha_fin : m), tareas[0].fecha_fin);
    const ini = aFecha(min);
    ini.setDate(ini.getDate() - 3);
    return { inicio: ini, totalDias: dias(ini, aFecha(max)) + 7 };
  }, [tareas]);

  const x = (iso: string) => dias(inicio, aFecha(iso)) * pxDia;
  const ancho = totalDias * pxDia;
  const alto = tareas.length * ALTO_FILA + 26;

  const desplazamiento = (id: string) =>
    arrastre?.id === id ? Math.round(arrastre.dx / pxDia) * pxDia : 0;

  function soltar(t: Tarea) {
    if (!arrastre || arrastre.id !== t.id) return;
    const deltaDias = Math.round(arrastre.dx / pxDia);
    setArrastre(null);
    if (deltaDias === 0) return;
    const ini = aFecha(t.fecha_inicio);
    const fin = aFecha(t.fecha_fin);
    ini.setDate(ini.getDate() + deltaDias);
    fin.setDate(fin.getDate() + deltaDias);
    onMover(t.id, aIso(ini), aIso(fin));
  }

  // Marcas verticales: lunes (zoom día/semana) o día 1 del mes (zoom mes)
  const marcas: { x: number; texto: string }[] = [];
  for (let d = 0; d <= totalDias; d++) {
    const f = new Date(inicio.getTime() + d * DIA_MS);
    const esMarca = zoom === "mes" ? f.getDate() === 1 : f.getDay() === 1;
    if (esMarca)
      marcas.push({
        x: d * pxDia,
        texto: `${f.getDate()}/${f.getMonth() + 1}`,
      });
  }
  const xHoy = dias(inicio, hoy) * pxDia;
  const porId = new Map(tareas.map((t, i) => [t.id, { t, fila: i }]));

  return (
    <div className="tarjeta overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--borde)] px-4 py-2">
        <div className="text-xs text-[var(--tinta-suave)]">
          Arrastra una barra para reprogramarla · borde negro ={" "}
          <strong>ruta crítica</strong> · ◆ = hito
        </div>
        <div className="flex gap-1">
          {(Object.keys(ZOOMS) as Zoom[]).map((z) => (
            <button
              key={z}
              onClick={() => setZoom(z)}
              className={`rounded px-2 py-0.5 text-xs capitalize ${
                zoom === z ? "bg-[var(--tinta)] text-white" : "text-[var(--tinta-2)] hover:bg-black/5"
              }`}
            >
              {z}
            </button>
          ))}
        </div>
      </div>

      <div className="flex">
        {/* Columna de títulos */}
        <div className="w-56 shrink-0 border-r border-[var(--borde)]" style={{ paddingTop: 26 }}>
          {tareas.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-1 truncate px-3 text-xs"
              style={{ height: ALTO_FILA }}
              title={t.titulo}
            >
              {t.es_hito && <span aria-hidden>◆</span>}
              <span className={t.estado === "hecha" ? "text-[var(--tinta-suave)] line-through" : ""}>
                {t.titulo}
              </span>
            </div>
          ))}
        </div>

        {/* Área de barras */}
        <div ref={contenedor} className="overflow-x-auto">
          <svg width={ancho} height={alto} className="block select-none">
            {/* Rejilla */}
            {marcas.map((m) => (
              <g key={m.x}>
                <line x1={m.x} y1={22} x2={m.x} y2={alto} stroke="var(--grid)" />
                <text x={m.x + 3} y={14} fontSize={10} fill="var(--tinta-suave)">
                  {m.texto}
                </text>
              </g>
            ))}
            {/* Dependencias */}
            {tareas.map((t, fila) =>
              t.dependencias.map((dep) => {
                const origen = porId.get(dep);
                if (!origen) return null;
                const x1 = x(origen.t.fecha_fin) + pxDia + desplazamiento(dep);
                const y1 = origen.fila * ALTO_FILA + 26 + ALTO_FILA / 2 - 4;
                const x2 = x(t.fecha_inicio) + desplazamiento(t.id);
                const y2 = fila * ALTO_FILA + 26 + ALTO_FILA / 2 - 4;
                const xm = Math.max(x1 + 6, x2 - 6);
                return (
                  <path
                    key={t.id + dep}
                    d={`M ${x1} ${y1} L ${xm} ${y1} L ${xm} ${y2} L ${x2} ${y2}`}
                    fill="none"
                    stroke="var(--eje)"
                    strokeWidth={1}
                  />
                );
              }),
            )}
            {/* Línea de hoy */}
            {xHoy >= 0 && xHoy <= ancho && (
              <g>
                <line x1={xHoy} y1={22} x2={xHoy} y2={alto} stroke="var(--acento)" strokeWidth={1.5} />
                <text x={xHoy + 4} y={32} fontSize={9} fill="var(--acento)" fontWeight={600}>
                  HOY
                </text>
              </g>
            )}
            {/* Barras e hitos */}
            {tareas.map((t, fila) => {
              const dxDrag = desplazamiento(t.id);
              const y = fila * ALTO_FILA + 26 + 7;
              const esCritica = criticas.has(t.id);
              const comun = {
                onPointerDown: (e: React.PointerEvent) => {
                  (e.target as Element).setPointerCapture(e.pointerId);
                  setArrastre({ id: t.id, x0: e.clientX, dx: 0 });
                },
                onPointerMove: (e: React.PointerEvent) => {
                  if (arrastre?.id === t.id)
                    setArrastre({ ...arrastre, dx: e.clientX - arrastre.x0 });
                },
                onPointerUp: () => soltar(t),
                style: { cursor: "grab" } as const,
              };
              if (t.es_hito) {
                const cx = x(t.fecha_fin) + pxDia / 2 + dxDrag;
                return (
                  <g key={t.id} {...comun}>
                    <title>{`${t.titulo} · ${t.fecha_fin}`}</title>
                    <rect
                      x={cx - 7}
                      y={y + 1}
                      width={14}
                      height={14}
                      transform={`rotate(45 ${cx} ${y + 8})`}
                      fill={t.estado === "hecha" ? "var(--tinta-suave)" : "var(--tinta)"}
                      stroke={esCritica ? "var(--tinta)" : "none"}
                      strokeWidth={2}
                    />
                  </g>
                );
              }
              const xi = x(t.fecha_inicio) + dxDrag;
              const w = Math.max(pxDia, x(t.fecha_fin) - x(t.fecha_inicio) + pxDia);
              return (
                <g key={t.id} {...comun}>
                  <title>{`${t.titulo} · ${t.fecha_inicio} → ${t.fecha_fin}`}</title>
                  <rect
                    x={xi}
                    y={y}
                    width={w}
                    height={16}
                    rx={4}
                    fill={t.proyecto_color}
                    opacity={t.estado === "hecha" ? 0.35 : 0.9}
                    stroke={esCritica ? "var(--tinta)" : "none"}
                    strokeWidth={1.8}
                  />
                  {t.estado === "hecha" && (
                    <text x={xi + w + 4} y={y + 12} fontSize={10} fill="var(--tinta-suave)">
                      ✓
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}
