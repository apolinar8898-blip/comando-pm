import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Etapa, Prospecto, TableroCaptacion } from "../tipos";
import { fechaCorta } from "../componentes/Chips";
import { ETAPAS, mxn, ORIGENES, TEXTO_ALERTA, TEXTO_ETAPA } from "../componentes/captacion";
import FichaProspecto, { moverEtapa } from "../componentes/FichaProspecto";
import RegistrarInteraccion from "../componentes/RegistrarInteraccion";

// Captación SINPROTEK (Fase 1): meta de 3 clientes pagando al 31/12/2026.
// KPIs calculados en el backend (dominio/captacion.py) + kanban por etapa
// con arrastre y fallback de toque (como Eisenhower).

export default function Captacion() {
  const [datos, setDatos] = useState<TableroCaptacion | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [registrar, setRegistrar] = useState<Prospecto | null>(null);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [sobre, setSobre] = useState<Etapa | null>(null);
  const [nuevo, setNuevo] = useState(false);

  const cargar = useCallback(async () => {
    setDatos(await api.get<TableroCaptacion>("/api/captacion"));
  }, []);

  useEffect(() => {
    cargar().catch(() => {});
  }, [cargar]);

  if (!datos) return <p className="text-sm text-[var(--tinta-suave)]">Cargando…</p>;
  const { kpis, prospectos } = datos;

  async function mover(id: string, etapa: Etapa) {
    setSeleccion(null);
    const p = prospectos.find((x) => x.id === id);
    if (p && (await moverEtapa(p, etapa).catch(() => false))) await cargar();
  }

  const ritmoPct = kpis.ritmo === null ? null : Math.round(kpis.ritmo * 100);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Captación</h1>
        <button
          onClick={() => setNuevo(true)}
          className="min-h-11 rounded-lg bg-[var(--tinta)] px-4 text-sm font-semibold text-white"
        >
          + Prospecto
        </button>
      </div>

      {/* ---------- KPIs ---------- */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi
          titulo="Clientes ganados"
          valor={`${kpis.ganados}/${kpis.meta_clientes}`}
          detalle={`${kpis.dias_restantes} días al 31/12`}
          alerta={kpis.ganados < kpis.meta_clientes}
        />
        <Kpi titulo="MRR actual" valor={mxn(kpis.mrr_actual)} detalle="mensualidades ganadas" />
        <Kpi titulo="MRR ponderado" valor={mxn(kpis.mrr_ponderado)} detalle="pipeline × probabilidad" />
        <Kpi
          titulo="Interacciones semana"
          valor={`${kpis.interacciones_semana}/${kpis.meta_semana}`}
          detalle={ritmoPct === null ? "ritmo: desde el martes" : `ritmo ${ritmoPct}% de lo esperado`}
          alerta={ritmoPct !== null && ritmoPct < 50}
        />
        <Kpi
          titulo="🔴 Alertas"
          valor={String(kpis.con_alerta)}
          detalle={`${kpis.acciones_vencidas} vencidas · ${kpis.sin_contacto} sin contacto`}
          alerta={kpis.con_alerta > 0}
        />
      </div>

      {/* ---------- Kanban ---------- */}
      <p className="text-xs text-[var(--tinta-suave)]">
        Arrastra una tarjeta a otra etapa, o tócala para moverla o abrir su ficha.
      </p>
      <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2">
        {ETAPAS.map((e) => {
          const propios = prospectos.filter((p) => p.etapa === e.clave);
          return (
            <section
              key={e.clave}
              onDragOver={(ev) => {
                ev.preventDefault();
                setSobre(e.clave);
              }}
              onDragLeave={() => setSobre(null)}
              onDrop={(ev) => {
                ev.preventDefault();
                setSobre(null);
                mover(ev.dataTransfer.getData("texto/prospecto"), e.clave);
              }}
              className={`tarjeta w-64 shrink-0 snap-start p-2 transition-colors ${sobre === e.clave ? "bg-black/[.04]" : ""}`}
            >
              <header className="mb-2 flex items-baseline justify-between px-1">
                <h2 className="text-sm font-bold">{e.texto}</h2>
                <span className="text-xs text-[var(--tinta-suave)]">{propios.length}</span>
              </header>
              <ul className="space-y-2">
                {propios.map((p) => (
                  <li
                    key={p.id}
                    draggable
                    onDragStart={(ev) => ev.dataTransfer.setData("texto/prospecto", p.id)}
                    onClick={() => setSeleccion(seleccion === p.id ? null : p.id)}
                    className="cursor-grab rounded-lg border border-[var(--borde)] bg-[var(--plano)] px-3 py-2 active:cursor-grabbing"
                    style={p.alertas.length ? { borderLeft: "4px solid var(--critico)" } : undefined}
                  >
                    <p className="text-sm font-semibold">{p.empresa}</p>
                    {p.contacto && <p className="text-xs text-[var(--tinta-2)]">{p.contacto}</p>}
                    {p.fecha_proxima_accion && (
                      <p className="mt-1 text-xs">
                        → {p.proxima_accion || "Seguimiento"} · {fechaCorta(p.fecha_proxima_accion)}
                      </p>
                    )}
                    {p.alertas.length > 0 && (
                      <p className="mt-1 text-xs font-medium text-[var(--critico)]">
                        🔴 {p.alertas.map((a) => TEXTO_ALERTA[a]).join(" · ")}
                      </p>
                    )}
                    <p className="mt-1 text-[11px] text-[var(--tinta-suave)]">
                      {ORIGENES[p.origen]} · {mxn(p.monto_mensual)}/mes
                    </p>
                    {seleccion === p.id && (
                      <div className="mt-2 space-y-2" onClick={(ev) => ev.stopPropagation()}>
                        <div className="flex gap-2">
                          <button
                            onClick={() => setRegistrar(p)}
                            className="min-h-10 flex-1 rounded-lg bg-[var(--acento)] text-xs font-semibold text-white"
                          >
                            Registrar
                          </button>
                          <button
                            onClick={() => setAbierto(p.id)}
                            className="min-h-10 flex-1 rounded-lg border border-[var(--borde)] text-xs font-semibold"
                          >
                            Ficha
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <span className="w-full text-[11px] text-[var(--tinta-suave)]">Mover a:</span>
                          {ETAPAS.filter((o) => o.clave !== p.etapa).map((o) => (
                            <button
                              key={o.clave}
                              onClick={() => mover(p.id, o.clave)}
                              className="min-h-9 rounded border border-[var(--borde)] bg-[var(--superficie)] px-2 text-[11px] font-semibold"
                            >
                              {o.corto}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </li>
                ))}
                {propios.length === 0 && (
                  <li className="rounded-lg border border-dashed border-[var(--grid)] px-3 py-3 text-center text-[11px] text-[var(--tinta-suave)]">
                    Suelta aquí
                  </li>
                )}
              </ul>
            </section>
          );
        })}
      </div>

      {/* ---------- Conversión y meta ---------- */}
      <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
        <section className="tarjeta p-4">
          <h2 className="mb-2 text-sm font-semibold">Conversión etapa a etapa</h2>
          <table className="w-full text-sm">
            <tbody>
              {kpis.conversion.map((f) => (
                <tr key={f.de} className="border-t border-[var(--grid)] first:border-0">
                  <td className="py-1.5 pr-2">
                    {TEXTO_ETAPA[f.de]} → {TEXTO_ETAPA[f.a]}
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-[var(--tinta-2)]">
                    {f.pasaron}/{f.llegaron}
                  </td>
                  <td className="w-14 py-1.5 text-right font-semibold tabular-nums">{f.pct === null ? "—" : `${f.pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <MetaSemanal actual={datos.config.meta_interacciones_semana} onCambio={cargar} />
      </div>

      {nuevo && <NuevoProspecto onCerrar={() => setNuevo(false)} onCreado={(id) => { setNuevo(false); cargar(); setAbierto(id); }} />}
      {abierto && <FichaProspecto id={abierto} onCerrar={() => { setAbierto(null); cargar().catch(() => {}); }} />}
      {registrar && (
        <RegistrarInteraccion
          prospectoId={registrar.id}
          empresa={registrar.empresa}
          onCerrar={() => setRegistrar(null)}
          onListo={() => {
            setRegistrar(null);
            setSeleccion(null);
            cargar().catch(() => {});
          }}
        />
      )}
    </div>
  );
}

function Kpi({ titulo, valor, detalle, alerta }: { titulo: string; valor: string; detalle?: string; alerta?: boolean }) {
  return (
    <div className="tarjeta px-3 py-2.5" style={alerta ? { borderLeft: "4px solid var(--critico)" } : undefined}>
      <p className="text-xs text-[var(--tinta-suave)]">{titulo}</p>
      <p className="text-2xl font-bold tabular-nums">{valor}</p>
      {detalle && <p className="text-[11px] text-[var(--tinta-2)]">{detalle}</p>}
    </div>
  );
}

function MetaSemanal({ actual, onCambio }: { actual: number; onCambio: () => void }) {
  const [meta, setMeta] = useState(actual);
  return (
    <section className="tarjeta space-y-2 p-4">
      <h2 className="text-sm font-semibold">Meta semanal de interacciones</h2>
      <div className="flex gap-2">
        <input
          type="number"
          min={1}
          value={meta}
          onChange={(e) => setMeta(Number(e.target.value))}
          className="w-24 rounded-lg border border-[var(--borde)] px-3 py-2 text-base"
          aria-label="Meta semanal"
        />
        <button
          disabled={meta === actual || meta < 1}
          onClick={async () => {
            await api.put("/api/captacion/config", { meta_interacciones_semana: meta }).catch(() => {});
            onCambio();
          }}
          className="min-h-11 rounded-lg bg-[var(--tinta)] px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          Guardar
        </button>
      </div>
      <p className="text-xs text-[var(--tinta-suave)]">Semáforo 🔴 si el ritmo baja del 50 % de lo esperado a la fecha.</p>
    </section>
  );
}

function NuevoProspecto({ onCerrar, onCreado }: { onCerrar: () => void; onCreado: (id: string) => void }) {
  const [f, setF] = useState({
    empresa: "",
    contacto: "",
    telefono: "",
    segmento: "pyme",
    origen: "canacintra",
    proxima_accion: "Llamar",
    fecha_proxima_accion: "",
  });
  const cambiar = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.value });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    const p = await api
      .post<Prospecto>("/api/captacion/prospectos", { ...f, fecha_proxima_accion: f.fecha_proxima_accion || null })
      .catch(() => null);
    if (p) onCreado(p.id);
  }

  const campo = "mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-3 py-2 text-base";
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center" onClick={onCerrar}>
      <form
        onSubmit={crear}
        onClick={(e) => e.stopPropagation()}
        className="tarjeta max-h-[92vh] w-full max-w-lg space-y-3 overflow-y-auto rounded-b-none p-4 sm:rounded-b-xl"
      >
        <h2 className="text-lg font-bold">Nuevo prospecto</h2>
        <label className="block text-sm font-semibold">
          Empresa o nombre
          <input autoFocus required value={f.empresa} onChange={cambiar("empresa")} className={campo} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm font-semibold">
            Contacto
            <input value={f.contacto} onChange={cambiar("contacto")} className={campo} />
          </label>
          <label className="block text-sm font-semibold">
            Teléfono
            <input type="tel" value={f.telefono} onChange={cambiar("telefono")} className={campo} />
          </label>
          <label className="block text-sm font-semibold">
            Segmento
            <select value={f.segmento} onChange={cambiar("segmento")} className={campo}>
              <option value="pyme">PyME ($4,000 + $4,000/mes)</option>
              <option value="independiente">Independiente ($3,000 + $3,500/mes)</option>
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Origen
            <select value={f.origen} onChange={cambiar("origen")} className={campo}>
              {Object.entries(ORIGENES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Próxima acción
            <input value={f.proxima_accion} onChange={cambiar("proxima_accion")} className={campo} />
          </label>
          <label className="block text-sm font-semibold">
            Fecha
            <input type="date" value={f.fecha_proxima_accion} onChange={cambiar("fecha_proxima_accion")} className={campo} />
          </label>
        </div>
        <div className="flex gap-2">
          <button className="min-h-11 flex-1 rounded-lg bg-[var(--tinta)] text-base font-semibold text-white">Crear</button>
          <button type="button" onClick={onCerrar} className="min-h-11 px-4 text-base text-[var(--tinta-2)]">
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
