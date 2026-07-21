import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DetalleProyecto, Documento, TipoDocumento } from "../tipos";
import { fechaCorta } from "./Chips";

// Documentos estratégicos (CLAUDE.md §5): formularios guiados + vista de
// lectura imprimible. Cada guardado crea una versión nueva (historial JSONB).

const CAMPOS_CHARTER: [string, string][] = [
  ["justificacion", "Justificación del proyecto"],
  ["alcance_incluye", "Alcance — SÍ incluye"],
  ["alcance_no_incluye", "Alcance — NO incluye (explícito)"],
  ["entregables", "Entregables principales"],
  ["supuestos", "Supuestos"],
  ["restricciones", "Restricciones"],
  ["riesgos_iniciales", "Riesgos iniciales"],
  ["criterios_exito", "Criterios de éxito"],
  ["interesados", "Interesados clave"],
];

const CAMPOS_CANVAS: [string, string][] = [
  ["proposito", "Propósito"],
  ["entregables", "Entregables"],
  ["hitos", "Hitos"],
  ["recursos", "Requisitos / recursos"],
  ["equipo", "Equipo / aliados"],
  ["riesgos", "Riesgos"],
  ["restricciones", "Restricciones"],
  ["presupuesto", "Presupuesto"],
  ["criterios_exito", "Criterios de éxito"],
];

const FUERZAS_PORTER: [string, string][] = [
  ["competidores", "Rivalidad entre competidores"],
  ["entrantes", "Amenaza de nuevos entrantes"],
  ["sustitutos", "Amenaza de sustitutos"],
  ["proveedores", "Poder de los proveedores"],
  ["clientes", "Poder de los clientes"],
];

const NOMBRE_TIPO: Record<string, string> = {
  charter: "Acta de constitución (Charter)",
  canvas: "Canvas de proyecto",
  porter: "5 fuerzas de Porter",
  rca: "Análisis causa raíz (RCA)",
};

type Hito = { titulo: string; fecha: string };
type NodoPorque = { texto: string; hijos: NodoPorque[] };
type Seleccion = { id?: string; tipo: TipoDocumento; contenido: Record<string, any>; version: number };

export default function Documentos({ detalle, recargar }: { detalle: DetalleProyecto; recargar: () => Promise<void> }) {
  const pid = detalle.proyecto.id;
  const [docs, setDocs] = useState<Documento[]>([]);
  const [sel, setSel] = useState<Seleccion | null>(null);
  const [lectura, setLectura] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  const cargarDocs = useCallback(async () => {
    const r = await api.get<{ documentos: Documento[] }>(`/api/documentos?proyecto_id=${pid}`);
    setDocs(r.documentos);
  }, [pid]);

  useEffect(() => {
    cargarDocs();
  }, [cargarDocs]);

  function nuevo(tipo: TipoDocumento) {
    setError("");
    setAviso("");
    setLectura(false);
    const contenido =
      tipo === "porter" ? { fuerzas: {} }
      : tipo === "rca" ? { porques: [], acciones: [], linea_tiempo: [] }
      : {};
    setSel({ tipo, contenido, version: 0 });
  }

  function abrir(d: Documento) {
    setError("");
    setAviso("");
    setSel({ id: d.id, tipo: d.tipo, contenido: structuredClone(d.contenido), version: d.version });
  }

  async function guardar() {
    if (!sel) return;
    setError("");
    try {
      const doc = sel.id
        ? await api.put<Documento>(`/api/documentos/${sel.id}`, { contenido: sel.contenido })
        : await api.post<Documento>("/api/documentos", { proyecto_id: pid, tipo: sel.tipo, contenido: sel.contenido });
      await cargarDocs();
      setSel({ id: doc.id, tipo: doc.tipo, contenido: structuredClone(doc.contenido), version: doc.version });
      setAviso(`Guardado como versión ${doc.version}.`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function sembrar() {
    if (!sel?.id) return;
    setError("");
    try {
      const r = await api.post<{ hitos_creados: number; hitos_existentes: number }>(`/api/documentos/${sel.id}/sembrar`);
      await Promise.all([cargarDocs(), recargar()]);
      setSel((s) => (s ? { ...s, contenido: { ...s.contenido, sembrado: true } } : s));
      setAviso(
        `Plan sembrado: ${r.hitos_creados} hito(s) creado(s) en el Gantt` +
          (r.hitos_existentes ? ` (${r.hitos_existentes} ya existían).` : "."),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function sembrarAcciones() {
    if (!sel?.id) return;
    setError("");
    try {
      const r = await api.post<{ tareas_creadas: number; ya_existian: number }>(`/api/documentos/${sel.id}/sembrar-acciones`);
      await Promise.all([cargarDocs(), recargar()]);
      setSel((s) => (s ? { ...s, contenido: { ...s.contenido, acciones_sembradas: true } } : s));
      setAviso(
        `${r.tareas_creadas} tarea(s) correctiva(s) creada(s)` +
          (r.ya_existian ? ` (${r.ya_existian} ya existían).` : "."),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function borrar(d: Documento) {
    if (!confirm(`¿Borrar ${NOMBRE_TIPO[d.tipo] ?? d.tipo} v${d.version}?`)) return;
    await api.del(`/api/documentos/${d.id}`);
    if (sel?.id === d.id) setSel(null);
    await cargarDocs();
  }

  const pon = (clave: string, valor: any) =>
    setSel((s) => (s ? { ...s, contenido: { ...s.contenido, [clave]: valor } } : s));

  return (
    <div className="space-y-4">
      <ObjetivosSmart detalle={detalle} recargar={recargar} />
      <FaseProyecto detalle={detalle} recargar={recargar} />

      <div className="tarjeta p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Documentos estratégicos</h3>
          <div className="flex gap-2">
            {(["charter", "canvas", "porter", "rca"] as TipoDocumento[]).map((t) => (
              <button key={t} onClick={() => nuevo(t)} className="rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs font-medium hover:bg-black/5">
                ＋ {t === "charter" ? "Charter" : t === "canvas" ? "Canvas" : t === "porter" ? "Porter" : "RCA"}
              </button>
            ))}
          </div>
        </div>

        {docs.length === 0 && !sel && (
          <p className="text-xs text-[var(--tinta-suave)]">
            Sin documentos aún. El charter completo es para proyectos grandes; el canvas es el "charter exprés".
          </p>
        )}

        {docs.length > 0 && (
          <ul className="mb-3 flex flex-wrap gap-2">
            {docs.map((d) => (
              <li key={d.id}>
                <button
                  onClick={() => abrir(d)}
                  className={`rounded-full border px-3 py-1 text-xs ${sel?.id === d.id ? "border-[var(--acento)] bg-[var(--acento)]/10 font-semibold" : "border-[var(--borde)] hover:bg-black/5"}`}
                >
                  {NOMBRE_TIPO[d.tipo] ?? d.tipo} · v{d.version}
                  {d.tipo === "charter" && d.contenido.sembrado && " · ✓ sembrado"}
                </button>
                <button onClick={() => borrar(d)} className="ml-1 text-[var(--tinta-suave)] hover:text-[var(--critico)]" title="Borrar documento">
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        {sel && (
          <div className="space-y-3 border-t border-[var(--grid)] pt-3">
            <div className="no-imprimir flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-bold">
                {NOMBRE_TIPO[sel.tipo]} {sel.id ? `· v${sel.version}` : "· borrador"}
              </h4>
              <div className="flex gap-2">
                <button onClick={() => setLectura(!lectura)} className="rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs hover:bg-black/5">
                  {lectura ? "✎ Editar" : "📄 Vista lectura"}
                </button>
                {lectura && (
                  <button onClick={() => window.print()} className="rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs hover:bg-black/5">
                    🖨 Imprimir / PDF
                  </button>
                )}
                {!lectura && (
                  <button onClick={guardar} className="rounded-lg bg-[var(--tinta)] px-3 py-1 text-xs font-medium text-white">
                    Guardar {sel.id ? `(→ v${sel.version + 1})` : ""}
                  </button>
                )}
              </div>
            </div>

            {error && <p className="no-imprimir text-xs font-medium text-[var(--critico)]">{error}</p>}
            {aviso && <p className="no-imprimir text-xs font-medium text-[var(--ok)]">{aviso}</p>}

            {lectura ? (
              <VistaLectura sel={sel} nombreProyecto={detalle.proyecto.nombre} tareas={detalle.tareas} />
            ) : (
              <>
                {sel.tipo === "charter" && <FormCharter sel={sel} pon={pon} sembrar={sembrar} />}
                {sel.tipo === "canvas" && <FormCampos campos={CAMPOS_CANVAS} sel={sel} pon={pon} columnas />}
                {sel.tipo === "porter" && <FormPorter sel={sel} pon={pon} />}
                {sel.tipo === "rca" && <FormRca sel={sel} pon={pon} sembrarAcciones={sembrarAcciones} tareas={detalle.tareas} />}
              </>
            )}
          </div>
        )}
      </div>

      <CierreProyecto detalle={detalle} recargar={recargar} />
    </div>
  );
}

// ---------- Objetivos SMART ----------

function ObjetivosSmart({ detalle, recargar }: { detalle: DetalleProyecto; recargar: () => Promise<void> }) {
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState("");
  const hoyIso = new Date().toISOString().slice(0, 10);
  const [forma, setForma] = useState({
    especifico: "", metrica: "", valor_objetivo: 0, valor_actual: 0,
    alcanzable: "", relevante: "", fecha_limite: hoyIso,
  });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post(`/api/proyectos/${detalle.proyecto.id}/objetivos`, forma);
      setCreando(false);
      setForma({ ...forma, especifico: "", metrica: "", valor_objetivo: 0 });
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function actualizarValor(oid: string, valor: number) {
    await api.patch(`/api/objetivos/${oid}`, { valor_actual: valor });
    await recargar();
  }

  async function borrar(oid: string) {
    if (confirm("¿Borrar este objetivo?")) {
      await api.del(`/api/objetivos/${oid}`);
      await recargar();
    }
  }

  const campoCls = "mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm";

  return (
    <div className="tarjeta p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Objetivos SMART</h3>
        <button onClick={() => setCreando(!creando)} className="rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs font-medium hover:bg-black/5">
          {creando ? "Cancelar" : "＋ Nuevo objetivo"}
        </button>
      </div>

      {creando && (
        <form onSubmit={crear} className="mb-4 grid gap-3 rounded-lg border border-dashed border-[var(--grid)] p-3 sm:grid-cols-2">
          <label className="text-xs text-[var(--tinta-2)] sm:col-span-2">
            <strong>S</strong>specífico — ¿qué se quiere lograr exactamente?
            <input required value={forma.especifico} onChange={(e) => setForma({ ...forma, especifico: e.target.value })} className={campoCls} />
          </label>
          <label className="text-xs text-[var(--tinta-2)]">
            <strong>M</strong>edible — métrica
            <input required value={forma.metrica} onChange={(e) => setForma({ ...forma, metrica: e.target.value })} className={campoCls} placeholder="ej. ventas/semana" />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-[var(--tinta-2)]">
              Valor objetivo
              <input required type="number" min={0.01} step="any" value={forma.valor_objetivo || ""} onChange={(e) => setForma({ ...forma, valor_objetivo: Number(e.target.value) })} className={campoCls} />
            </label>
            <label className="text-xs text-[var(--tinta-2)]">
              Valor actual
              <input type="number" step="any" value={forma.valor_actual} onChange={(e) => setForma({ ...forma, valor_actual: Number(e.target.value) })} className={campoCls} />
            </label>
          </div>
          <label className="text-xs text-[var(--tinta-2)]">
            <strong>A</strong>lcanzable — ¿por qué es posible?
            <input required value={forma.alcanzable} onChange={(e) => setForma({ ...forma, alcanzable: e.target.value })} className={campoCls} />
          </label>
          <label className="text-xs text-[var(--tinta-2)]">
            <strong>R</strong>elevante — ¿por qué importa?
            <input required value={forma.relevante} onChange={(e) => setForma({ ...forma, relevante: e.target.value })} className={campoCls} />
          </label>
          <label className="text-xs text-[var(--tinta-2)]">
            <strong>T</strong>emporal — fecha límite
            <input required type="date" value={forma.fecha_limite} onChange={(e) => setForma({ ...forma, fecha_limite: e.target.value })} className={campoCls} />
          </label>
          {error && <p className="text-xs font-medium text-[var(--critico)] sm:col-span-2">{error}</p>}
          <button type="submit" className="rounded-lg bg-[var(--tinta)] px-4 py-2 text-sm font-medium text-white sm:col-span-2">
            Guardar objetivo
          </button>
        </form>
      )}

      {detalle.objetivos.length === 0 && !creando && (
        <p className="text-xs text-[var(--tinta-suave)]">Sin objetivos aún. La validación es dura: sin métrica numérica no se guarda.</p>
      )}

      <ul className="space-y-3">
        {detalle.objetivos.map((o) => {
          const pct = Math.min(100, (o.valor_actual / o.valor_objetivo) * 100);
          return (
            <li key={o.id}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium">{o.especifico}</p>
                <button onClick={() => borrar(o.id)} className="text-[var(--tinta-suave)] hover:text-[var(--critico)]" title="Borrar objetivo">✕</button>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-black/10">
                <div className="h-full rounded-full bg-[var(--acento)]" style={{ width: `${pct}%` }} />
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[var(--tinta-suave)]">
                <span>{o.metrica}:</span>
                <input
                  type="number"
                  step="any"
                  defaultValue={o.valor_actual}
                  key={`${o.id}-${o.valor_actual}`}
                  onBlur={(e) => Number(e.target.value) !== o.valor_actual && actualizarValor(o.id, Number(e.target.value))}
                  className="w-16 rounded border border-[var(--borde)] px-1 py-0.5 text-[10px]"
                  aria-label={`Valor actual de ${o.metrica}`}
                />
                <span>/ {o.valor_objetivo} ({Math.round(pct)}%) · límite {fechaCorta(o.fecha_limite)}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------- Fase del proyecto (anotación del roadmap, §5.5) ----------

function FaseProyecto({ detalle, recargar }: { detalle: DetalleProyecto; recargar: () => Promise<void> }) {
  const p = detalle.proyecto as any;
  const [forma, setForma] = useState({ fase: p.fase ?? "", fase_inicio: p.fase_inicio ?? "", fase_fin: p.fase_fin ?? "" });

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    await api.patch(`/api/proyectos/${detalle.proyecto.id}`, {
      fase: forma.fase,
      fase_inicio: forma.fase_inicio || null,
      fase_fin: forma.fase_fin || null,
    });
    await recargar();
  }

  return (
    <form onSubmit={guardar} className="tarjeta flex flex-wrap items-end gap-3 p-4">
      <label className="flex-1 text-xs text-[var(--tinta-2)]">
        Fase actual (se muestra en el roadmap)
        <input value={forma.fase} onChange={(e) => setForma({ ...forma, fase: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm" placeholder="ej. Descubrimiento, Construcción, Lanzamiento…" />
      </label>
      <label className="text-xs text-[var(--tinta-2)]">
        Inicio de fase
        <input type="date" value={forma.fase_inicio} onChange={(e) => setForma({ ...forma, fase_inicio: e.target.value })} className="mt-1 block rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
      </label>
      <label className="text-xs text-[var(--tinta-2)]">
        Fin de fase
        <input type="date" value={forma.fase_fin} onChange={(e) => setForma({ ...forma, fase_fin: e.target.value })} className="mt-1 block rounded-lg border border-[var(--borde)] px-2 py-2 text-sm" />
      </label>
      <button type="submit" className="rounded-lg border border-[var(--borde)] px-3 py-2 text-xs font-medium hover:bg-black/5">
        Guardar fase
      </button>
    </form>
  );
}

// ---------- Formularios ----------

function FormCampos({ campos, sel, pon, columnas }: { campos: [string, string][]; sel: Seleccion; pon: (k: string, v: any) => void; columnas?: boolean }) {
  return (
    <div className={columnas ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-3" : "space-y-3"}>
      {campos.map(([clave, etiqueta]) => (
        <label key={clave} className="block text-xs text-[var(--tinta-2)]">
          {etiqueta}
          <textarea
            value={sel.contenido[clave] ?? ""}
            onChange={(e) => pon(clave, e.target.value)}
            rows={columnas ? 3 : 2}
            className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm"
          />
        </label>
      ))}
    </div>
  );
}

function FormCharter({ sel, pon, sembrar }: { sel: Seleccion; pon: (k: string, v: any) => void; sembrar: () => void }) {
  const hitos: Hito[] = sel.contenido.hitos_alto_nivel ?? [];
  const ponHito = (i: number, cambio: Partial<Hito>) =>
    pon("hitos_alto_nivel", hitos.map((h, j) => (j === i ? { ...h, ...cambio } : h)));

  return (
    <div className="space-y-3">
      <FormCampos campos={CAMPOS_CHARTER} sel={sel} pon={pon} columnas />

      <div className="rounded-lg border border-[var(--grid)] p-3">
        <div className="mb-2 flex items-center justify-between">
          <h5 className="text-xs font-semibold">◆ Hitos de alto nivel</h5>
          <button
            type="button"
            onClick={() => pon("hitos_alto_nivel", [...hitos, { titulo: "", fecha: "" }])}
            className="rounded border border-[var(--borde)] px-2 py-0.5 text-xs hover:bg-black/5"
          >
            ＋ Hito
          </button>
        </div>
        {hitos.length === 0 && (
          <p className="text-[10px] text-[var(--tinta-suave)]">Agrega hitos con fecha: al confirmar el charter se convierten en tareas-hito reales del Gantt.</p>
        )}
        {hitos.map((h, i) => (
          <div key={i} className="mb-1.5 flex gap-2">
            <input
              value={h.titulo}
              onChange={(e) => ponHito(i, { titulo: e.target.value })}
              placeholder="Título del hito"
              className="flex-1 rounded-lg border border-[var(--borde)] px-3 py-1.5 text-sm"
            />
            <input
              type="date"
              value={h.fecha}
              onChange={(e) => ponHito(i, { fecha: e.target.value })}
              className="rounded-lg border border-[var(--borde)] px-2 py-1.5 text-sm"
            />
            <button type="button" onClick={() => pon("hitos_alto_nivel", hitos.filter((_, j) => j !== i))} className="px-1 text-[var(--tinta-suave)] hover:text-[var(--critico)]" title="Quitar hito">
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between rounded-lg border border-[var(--grid)] bg-[var(--plano)] p-3">
        <p className="text-[11px] text-[var(--tinta-2)]">
          {sel.contenido.sembrado
            ? "✓ Charter confirmado y plan sembrado. Los hitos viven en el Gantt."
            : "El charter no es papel muerto: al confirmarlo, sus hitos siembran el plan del proyecto."}
        </p>
        {!sel.contenido.sembrado && (
          <button
            type="button"
            onClick={sembrar}
            disabled={!sel.id}
            title={sel.id ? "" : "Guarda el charter primero"}
            className="rounded-lg bg-[var(--acento)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
          >
            Confirmar y sembrar hitos
          </button>
        )}
      </div>
    </div>
  );
}

function FormPorter({ sel, pon, soloLectura }: { sel: Seleccion; pon: (k: string, v: any) => void; soloLectura?: boolean }) {
  const fuerzas: Record<string, { intensidad?: number; notas?: string }> = sel.contenido.fuerzas ?? {};
  const ponFuerza = (clave: string, cambio: object) =>
    pon("fuerzas", { ...fuerzas, [clave]: { ...fuerzas[clave], ...cambio } });

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      {!soloLectura && (
        <div className="space-y-3">
          {FUERZAS_PORTER.map(([clave, etiqueta]) => (
            <div key={clave} className="rounded-lg border border-[var(--grid)] p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold">{etiqueta}</p>
                <select
                  value={fuerzas[clave]?.intensidad ?? 0}
                  onChange={(e) => ponFuerza(clave, { intensidad: Number(e.target.value) })}
                  className="rounded border border-[var(--borde)] px-1 py-0.5 text-xs"
                  aria-label={`Intensidad: ${etiqueta}`}
                >
                  <option value={0}>— intensidad</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>{n} — {["muy baja", "baja", "media", "alta", "muy alta"][n - 1]}</option>
                  ))}
                </select>
              </div>
              <textarea
                value={fuerzas[clave]?.notas ?? ""}
                onChange={(e) => ponFuerza(clave, { notas: e.target.value })}
                rows={2}
                placeholder="Notas / evidencia"
                className="mt-2 w-full rounded-lg border border-[var(--borde)] px-3 py-1.5 text-xs"
              />
            </div>
          ))}
        </div>
      )}
      <RadarPorter fuerzas={fuerzas} />
    </div>
  );
}

// Radar SVG propio (misma convención que GraficaAvance: sin librerías,
// una serie → sin leyenda, grid recesivo, etiquetas directas).
function RadarPorter({ fuerzas }: { fuerzas: Record<string, { intensidad?: number }> }) {
  const CX = 180, CY = 160, R = 105;
  const ang = (i: number) => ((-90 + i * 72) * Math.PI) / 180;
  const punto = (i: number, v: number): [number, number] => [
    CX + Math.cos(ang(i)) * R * (v / 5),
    CY + Math.sin(ang(i)) * R * (v / 5),
  ];
  const poligono = (v: number) => FUERZAS_PORTER.map((_, i) => punto(i, v).join(",")).join(" ");
  const valores = FUERZAS_PORTER.map(([clave]) => fuerzas[clave]?.intensidad ?? 0);
  const datos = FUERZAS_PORTER.map((_, i) => punto(i, valores[i]).join(",")).join(" ");
  const etiquetas = ["Competidores", "Entrantes", "Sustitutos", "Proveedores", "Clientes"];

  return (
    <div className="tarjeta p-2">
      <svg viewBox="0 0 360 320" className="w-full" role="img" aria-label="Radar de las 5 fuerzas de Porter">
        {[1, 2, 3, 4, 5].map((v) => (
          <polygon key={v} points={poligono(v)} fill="none" stroke="var(--grid)" />
        ))}
        {FUERZAS_PORTER.map((_, i) => (
          <line key={i} x1={CX} y1={CY} x2={punto(i, 5)[0]} y2={punto(i, 5)[1]} stroke="var(--grid)" />
        ))}
        <polygon points={datos} fill="var(--acento)" fillOpacity={0.22} stroke="var(--acento)" strokeWidth={2} />
        {FUERZAS_PORTER.map((_, i) =>
          valores[i] > 0 ? (
            <circle key={i} cx={punto(i, valores[i])[0]} cy={punto(i, valores[i])[1]} r={3.5} fill="var(--acento)" stroke="var(--superficie)" strokeWidth={2} />
          ) : null,
        )}
        {FUERZAS_PORTER.map((_, i) => {
          const [x, y] = punto(i, 6.1);
          const anchor = Math.abs(Math.cos(ang(i))) < 0.3 ? "middle" : Math.cos(ang(i)) > 0 ? "start" : "end";
          return (
            <text key={i} x={x} y={y + 3} fontSize={10} textAnchor={anchor} fill="var(--tinta-2)">
              {etiquetas[i]}
              <tspan fontWeight={700}> {valores[i] || "—"}</tspan>
            </text>
          );
        })}
      </svg>
      <p className="pb-1 text-center text-[10px] text-[var(--tinta-suave)]">Intensidad 0—5 por fuerza</p>
    </div>
  );
}

// ---------- RCA: 5 porqués ramificables + acciones que crean tareas ----------

// Actualiza el árbol de porqués por ruta de índices (clon inmutable simple).
function conRuta(nodos: NodoPorque[], ruta: number[], fn: (n: NodoPorque[]) => void): NodoPorque[] {
  const copia: NodoPorque[] = JSON.parse(JSON.stringify(nodos));
  let nivel = copia;
  for (const i of ruta) nivel = nivel[i].hijos;
  fn(nivel);
  return copia;
}

function hojas(nodos: NodoPorque[]): string[] {
  return nodos.flatMap((n) =>
    n.hijos.length === 0 ? (n.texto.trim() ? [n.texto.trim()] : []) : hojas(n.hijos),
  );
}

function ArbolPorques({ nodos, ruta, cambiar, nivel }: {
  nodos: NodoPorque[];
  ruta: number[];
  cambiar: (ruta: number[], fn: (n: NodoPorque[]) => void) => void;
  nivel: number;
}) {
  return (
    <ul className={nivel > 0 ? "ml-5 border-l border-[var(--grid)] pl-3" : ""}>
      {nodos.map((n, i) => (
        <li key={i} className="mt-1.5">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-[var(--tinta-suave)]">¿{nivel + 1}?</span>
            <input
              value={n.texto}
              onChange={(e) => cambiar(ruta, (arr) => { arr[i].texto = e.target.value; })}
              placeholder={nivel === 0 ? "¿Por qué pasó?" : "¿Y eso por qué?"}
              className="flex-1 rounded-lg border border-[var(--borde)] px-2.5 py-1.5 text-xs"
            />
            {nivel < 6 && (
              <button
                type="button"
                title="Preguntar por qué a esta causa"
                onClick={() => cambiar([...ruta, i], (arr) => { arr.push({ texto: "", hijos: [] }); })}
                className="rounded border border-[var(--borde)] px-1.5 py-1 text-[10px] font-semibold hover:bg-black/5"
              >
                ＋ ¿por qué?
              </button>
            )}
            <button
              type="button"
              title="Quitar (con sus ramas)"
              onClick={() => cambiar(ruta, (arr) => { arr.splice(i, 1); })}
              className="px-1 text-[var(--tinta-suave)] hover:text-[var(--critico)]"
            >
              ✕
            </button>
          </div>
          {n.hijos.length > 0 && <ArbolPorques nodos={n.hijos} ruta={[...ruta, i]} cambiar={cambiar} nivel={nivel + 1} />}
        </li>
      ))}
    </ul>
  );
}

function FormRca({ sel, pon, sembrarAcciones, tareas }: {
  sel: Seleccion;
  pon: (k: string, v: any) => void;
  sembrarAcciones: () => void;
  tareas: DetalleProyecto["tareas"];
}) {
  const porques: NodoPorque[] = sel.contenido.porques ?? [];
  const eventos: { fecha: string; evento: string }[] = sel.contenido.linea_tiempo ?? [];
  const acciones: Hito[] = sel.contenido.acciones ?? [];
  const verificacion = sel.contenido.verificacion ?? { senal: "", fecha: "" };
  const candidatas = hojas(porques);
  const delRca = tareas.filter((t) => t.origen_rca === sel.id);
  const cambiar = (ruta: number[], fn: (n: NodoPorque[]) => void) => pon("porques", conRuta(porques, ruta, fn));
  const campoCls = "mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm";

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-[var(--tinta-2)]">
          1 · ¿Qué pasó? (hecho, no interpretación)
          <textarea value={sel.contenido.que_paso ?? ""} onChange={(e) => pon("que_paso", e.target.value)} rows={2} className={campoCls} />
        </label>
        <label className="block text-xs text-[var(--tinta-2)]">
          Impacto medible (tiempo, dinero, clientes…)
          <textarea value={sel.contenido.impacto_medible ?? ""} onChange={(e) => pon("impacto_medible", e.target.value)} rows={2} className={campoCls} />
        </label>
      </div>

      <div className="rounded-lg border border-[var(--grid)] p-3">
        <div className="mb-1 flex items-center justify-between">
          <h5 className="text-xs font-semibold">2 · Línea de tiempo</h5>
          <button type="button" onClick={() => pon("linea_tiempo", [...eventos, { fecha: "", evento: "" }])} className="rounded border border-[var(--borde)] px-2 py-0.5 text-xs hover:bg-black/5">
            ＋ Evento
          </button>
        </div>
        {eventos.map((ev, i) => (
          <div key={i} className="mb-1.5 flex gap-2">
            <input type="date" value={ev.fecha} onChange={(e) => pon("linea_tiempo", eventos.map((x, j) => (j === i ? { ...x, fecha: e.target.value } : x)))} className="rounded-lg border border-[var(--borde)] px-2 py-1.5 text-xs" />
            <input value={ev.evento} onChange={(e) => pon("linea_tiempo", eventos.map((x, j) => (j === i ? { ...x, evento: e.target.value } : x)))} placeholder="Qué ocurrió" className="flex-1 rounded-lg border border-[var(--borde)] px-2.5 py-1.5 text-xs" />
            <button type="button" onClick={() => pon("linea_tiempo", eventos.filter((_, j) => j !== i))} className="px-1 text-[var(--tinta-suave)] hover:text-[var(--critico)]">✕</button>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-[var(--grid)] p-3">
        <div className="mb-1 flex items-center justify-between">
          <h5 className="text-xs font-semibold">3 · Los 5 porqués (ramifica si una causa tiene dos raíces)</h5>
          <button type="button" onClick={() => pon("porques", [...porques, { texto: "", hijos: [] }])} className="rounded border border-[var(--borde)] px-2 py-0.5 text-xs hover:bg-black/5">
            ＋ Causa
          </button>
        </div>
        {porques.length === 0 && <p className="text-[10px] text-[var(--tinta-suave)]">Empieza con "＋ Causa" y sigue preguntando por qué (mínimo 3 niveles, máximo 7).</p>}
        <ArbolPorques nodos={porques} ruta={[]} cambiar={cambiar} nivel={0} />
      </div>

      <label className="block text-xs text-[var(--tinta-2)]">
        4 · Causa raíz (elige una hoja de la cadena)
        <select value={sel.contenido.causa_raiz ?? ""} onChange={(e) => pon("causa_raiz", e.target.value)} className={campoCls}>
          <option value="">— sin elegir —</option>
          {candidatas.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>

      <div className="rounded-lg border border-[var(--grid)] p-3">
        <div className="mb-1 flex items-center justify-between">
          <h5 className="text-xs font-semibold">5 · Acciones correctivas (se vuelven tareas reales)</h5>
          <button type="button" onClick={() => pon("acciones", [...acciones, { titulo: "", fecha: "" }])} className="rounded border border-[var(--borde)] px-2 py-0.5 text-xs hover:bg-black/5">
            ＋ Acción
          </button>
        </div>
        {acciones.map((a, i) => (
          <div key={i} className="mb-1.5 flex gap-2">
            <input value={a.titulo} onChange={(e) => pon("acciones", acciones.map((x, j) => (j === i ? { ...x, titulo: e.target.value } : x)))} placeholder="Qué se hará para que no se repita" className="flex-1 rounded-lg border border-[var(--borde)] px-2.5 py-1.5 text-xs" />
            <input type="date" value={a.fecha} onChange={(e) => pon("acciones", acciones.map((x, j) => (j === i ? { ...x, fecha: e.target.value } : x)))} className="rounded-lg border border-[var(--borde)] px-2 py-1.5 text-xs" />
            <button type="button" onClick={() => pon("acciones", acciones.filter((_, j) => j !== i))} className="px-1 text-[var(--tinta-suave)] hover:text-[var(--critico)]">✕</button>
          </div>
        ))}
        <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
          <label className="block text-[10px] text-[var(--tinta-2)]">
            6 · ¿Cómo sabremos que no volvió a pasar? (crea una tarea de verificación futura)
            <input value={verificacion.senal} onChange={(e) => pon("verificacion", { ...verificacion, senal: e.target.value })} placeholder="Señal de verificación" className="mt-1 w-full rounded-lg border border-[var(--borde)] px-2.5 py-1.5 text-xs" />
          </label>
          <label className="block text-[10px] text-[var(--tinta-2)]">
            Fecha de revisión
            <input type="date" value={verificacion.fecha} onChange={(e) => pon("verificacion", { ...verificacion, fecha: e.target.value })} className="mt-1 block rounded-lg border border-[var(--borde)] px-2 py-1.5 text-xs" />
          </label>
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-[var(--grid)] bg-[var(--plano)] p-3">
        <p className="text-[11px] text-[var(--tinta-2)]">
          {sel.contenido.acciones_sembradas
            ? `✓ Acciones sembradas: ${delRca.length} tarea(s) en el proyecto.`
            : "El RCA debe terminar en tareas, no en un documento que nadie relee."}
        </p>
        <button
          type="button"
          onClick={sembrarAcciones}
          disabled={!sel.id}
          title={sel.id ? "" : "Guarda el RCA primero"}
          className="rounded-lg bg-[var(--acento)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
        >
          Crear tareas correctivas
        </button>
      </div>

      {delRca.length > 0 && (
        <ul className="space-y-1">
          {delRca.map((t) => (
            <li key={t.id} className="flex items-center gap-2 text-xs">
              <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${t.estado === "hecha" ? "bg-[var(--ok)]/15 text-[var(--ok)]" : "bg-black/10"}`}>
                {t.estado.replace("_", " ")}
              </span>
              <span className={t.estado === "hecha" ? "text-[var(--tinta-suave)] line-through" : ""}>{t.titulo}</span>
              <span className="text-[10px] text-[var(--tinta-suave)]">· {fechaCorta(t.fecha_fin)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- Cierre de proyecto (CLAUDE.md §6: nada se borra, se archiva) ----------

function CierreProyecto({ detalle, recargar }: { detalle: DetalleProyecto; recargar: () => Promise<void> }) {
  const p = detalle.proyecto;
  const [lecciones, setLecciones] = useState(p.lecciones ?? "");

  async function cerrar() {
    if (!confirm("¿Cerrar y archivar este proyecto? Seguirá consultable, pero saldrá del portafolio activo.")) return;
    await api.patch(`/api/proyectos/${p.id}`, { estado: "cerrado", lecciones });
    await recargar();
  }

  async function reabrir() {
    await api.patch(`/api/proyectos/${p.id}`, { estado: "activo" });
    await recargar();
  }

  if (p.estado === "cerrado") {
    return (
      <div className="tarjeta border-l-4 p-4" style={{ borderLeftColor: "var(--eje)" }}>
        <h3 className="text-sm font-semibold">Proyecto cerrado (archivado)</h3>
        {p.lecciones && <p className="mt-1 whitespace-pre-wrap text-xs text-[var(--tinta-2)]">Lecciones: {p.lecciones}</p>}
        <button onClick={reabrir} className="mt-2 rounded-lg border border-[var(--borde)] px-2.5 py-1 text-xs font-medium hover:bg-black/5">
          Reabrir proyecto
        </button>
      </div>
    );
  }

  return (
    <div className="tarjeta p-4">
      <h3 className="mb-1 text-sm font-semibold">Cerrar proyecto</h3>
      <p className="mb-2 text-[10px] text-[var(--tinta-suave)]">
        Estado final de objetivos: {detalle.objetivos.length === 0 ? "sin objetivos" : detalle.objetivos.map((o) => `${o.metrica} ${o.valor_actual}/${o.valor_objetivo}`).join(" · ")}
        {" "}· avance {detalle.kpis.avance_pct}%
      </p>
      <label className="block text-xs text-[var(--tinta-2)]">
        ¿Qué harías diferente? (lecciones aprendidas — valen oro después)
        <textarea value={lecciones} onChange={(e) => setLecciones(e.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-[var(--borde)] px-3 py-2 text-sm" />
      </label>
      <button onClick={cerrar} className="mt-2 rounded-lg border border-[var(--critico)] px-3 py-1.5 text-xs font-semibold text-[var(--critico)] hover:bg-[var(--critico)]/5">
        Cerrar y archivar
      </button>
    </div>
  );
}

// ---------- Vista de lectura imprimible ----------

function VistaLectura({ sel, nombreProyecto, tareas }: { sel: Seleccion; nombreProyecto: string; tareas: DetalleProyecto["tareas"] }) {
  const campos = sel.tipo === "charter" ? CAMPOS_CHARTER : CAMPOS_CANVAS;
  return (
    <article className="area-imprimible tarjeta space-y-4 p-6">
      <header className="border-b border-[var(--grid)] pb-3">
        <h1 className="text-lg font-bold">{NOMBRE_TIPO[sel.tipo]}</h1>
        <p className="text-xs text-[var(--tinta-suave)]">
          {nombreProyecto} · versión {sel.version || "borrador"} · {new Date().toLocaleDateString("es-MX")}
        </p>
      </header>

      {sel.tipo === "rca" ? (
        <LecturaRca sel={sel} tareas={tareas} />
      ) : sel.tipo === "porter" ? (
        <>
          <FormPorter sel={sel} pon={() => {}} soloLectura />
          <dl className="space-y-2">
            {FUERZAS_PORTER.map(([clave, etiqueta]) => {
              const f = (sel.contenido.fuerzas ?? {})[clave];
              return (
                <div key={clave}>
                  <dt className="text-xs font-semibold">
                    {etiqueta} — intensidad {f?.intensidad ?? "—"}/5
                  </dt>
                  {f?.notas && <dd className="text-xs text-[var(--tinta-2)]">{f.notas}</dd>}
                </div>
              );
            })}
          </dl>
        </>
      ) : (
        <dl className="space-y-3">
          {campos.map(([clave, etiqueta]) =>
            sel.contenido[clave] ? (
              <div key={clave}>
                <dt className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">{etiqueta}</dt>
                <dd className="whitespace-pre-wrap text-sm">{sel.contenido[clave]}</dd>
              </div>
            ) : null,
          )}
          {sel.tipo === "charter" && (sel.contenido.hitos_alto_nivel ?? []).length > 0 && (
            <div>
              <dt className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">Hitos de alto nivel</dt>
              <dd>
                <ul className="mt-1 space-y-0.5 text-sm">
                  {(sel.contenido.hitos_alto_nivel as Hito[]).map((h, i) => (
                    <li key={i}>◆ {h.titulo} — {h.fecha ? fechaCorta(h.fecha) : "sin fecha"}</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
        </dl>
      )}

      {sel.tipo === "charter" && (
        <footer className="border-t border-[var(--grid)] pt-3 text-xs text-[var(--tinta-2)]">
          {sel.contenido.sembrado ? "✓ Confirmado: los hitos fueron sembrados en el plan." : "Pendiente de confirmación."}
        </footer>
      )}
    </article>
  );
}

function CadenaLectura({ nodos, causaRaiz, nivel }: { nodos: NodoPorque[]; causaRaiz: string; nivel: number }) {
  return (
    <ul className={nivel > 0 ? "ml-4 border-l border-[var(--grid)] pl-3" : ""}>
      {nodos.map((n, i) => (
        <li key={i} className="mt-1 text-sm">
          <span className="text-[10px] font-bold text-[var(--tinta-suave)]">{nivel + 1}. ¿Por qué?</span>{" "}
          <span className={n.texto.trim() === causaRaiz ? "font-bold text-[var(--critico)]" : ""}>
            {n.texto || "—"}
            {n.texto.trim() === causaRaiz && " ← causa raíz"}
          </span>
          {n.hijos.length > 0 && <CadenaLectura nodos={n.hijos} causaRaiz={causaRaiz} nivel={nivel + 1} />}
        </li>
      ))}
    </ul>
  );
}

function LecturaRca({ sel, tareas }: { sel: Seleccion; tareas: DetalleProyecto["tareas"] }) {
  const c = sel.contenido;
  const delRca = tareas.filter((t) => t.origen_rca === sel.id);
  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">¿Qué pasó?</h2>
        <p className="whitespace-pre-wrap text-sm">{c.que_paso || "—"}</p>
        {c.impacto_medible && <p className="mt-1 text-xs text-[var(--tinta-2)]">Impacto: {c.impacto_medible}</p>}
      </section>

      {(c.linea_tiempo ?? []).length > 0 && (
        <section>
          <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">Línea de tiempo</h2>
          <ol className="mt-1 space-y-0.5 text-sm">
            {c.linea_tiempo.map((ev: { fecha: string; evento: string }, i: number) => (
              <li key={i}><strong className="text-xs">{ev.fecha ? fechaCorta(ev.fecha) : "—"}</strong> · {ev.evento}</li>
            ))}
          </ol>
        </section>
      )}

      <section>
        <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">Cadena de porqués</h2>
        {(c.porques ?? []).length === 0 ? <p className="text-sm">—</p> : <CadenaLectura nodos={c.porques} causaRaiz={c.causa_raiz ?? ""} nivel={0} />}
      </section>

      {c.causa_raiz && (
        <section className="rounded-lg border-l-4 bg-[var(--plano)] p-3" style={{ borderLeftColor: "var(--critico)" }}>
          <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">Causa raíz</h2>
          <p className="text-sm font-semibold">{c.causa_raiz}</p>
        </section>
      )}

      <section>
        <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">Acciones correctivas (estado real)</h2>
        {delRca.length === 0 ? (
          <p className="text-sm text-[var(--tinta-suave)]">Aún no se han creado las tareas correctivas.</p>
        ) : (
          <table className="mt-1 w-full text-sm">
            <tbody>
              {delRca.map((t) => (
                <tr key={t.id} className="border-b border-[var(--grid)] last:border-0">
                  <td className="py-1">{t.titulo}</td>
                  <td className="py-1 text-xs">{fechaCorta(t.fecha_fin)}</td>
                  <td className="py-1 text-xs font-semibold uppercase">{t.estado.replace("_", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {c.verificacion?.senal && (
        <section>
          <h2 className="text-xs font-bold uppercase tracking-wide text-[var(--tinta-2)]">¿Cómo sabremos que no volvió a pasar?</h2>
          <p className="text-sm">{c.verificacion.senal}{c.verificacion.fecha && ` · revisión ${fechaCorta(c.verificacion.fecha)}`}</p>
        </section>
      )}
    </div>
  );
}
