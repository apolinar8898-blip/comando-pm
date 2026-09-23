import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Etapa, Interaccion, Prospecto } from "../tipos";
import { fechaCorta } from "./Chips";
import { CANALES, ETAPAS, mxn, ORIGENES, SERVICIOS, TEXTO_ALERTA, TEXTO_ETAPA } from "./captacion";
import RegistrarInteraccion from "./RegistrarInteraccion";

// Ficha del prospecto: datos editables (se guardan al salir del campo),
// etapa, historial de interacciones y "Registrar interacción" (2 toques).

/** Mueve de etapa; "perdido" pide el motivo (obligatorio en el dominio). */
export async function moverEtapa(p: Prospecto, etapa: Etapa): Promise<boolean> {
  if (etapa === p.etapa) return false;
  let motivo = "";
  if (etapa === "perdido") {
    motivo = (window.prompt(`¿Por qué se perdió ${p.empresa}?`) ?? "").trim();
    if (!motivo) return false;
  }
  await api.patch(`/api/captacion/prospectos/${p.id}`, { etapa, ...(motivo ? { motivo_perdida: motivo } : {}) });
  return true;
}

type Campo = { clave: keyof Prospecto; texto: string; tipo?: string };
const CAMPOS: Campo[] = [
  { clave: "empresa", texto: "Empresa" },
  { clave: "contacto", texto: "Contacto" },
  { clave: "puesto", texto: "Puesto" },
  { clave: "telefono", texto: "Teléfono", tipo: "tel" },
  { clave: "correo", texto: "Correo", tipo: "email" },
  { clave: "giro", texto: "Giro" },
  { clave: "proxima_accion", texto: "Próxima acción" },
  { clave: "fecha_proxima_accion", texto: "Fecha próxima acción", tipo: "date" },
  { clave: "monto_desarrollo", texto: "Desarrollo (MXN)", tipo: "number" },
  { clave: "monto_mensual", texto: "Mensualidad (MXN)", tipo: "number" },
  { clave: "link_drive", texto: "Carpeta de Drive", tipo: "url" },
];

export default function FichaProspecto({ id, onCerrar }: { id: string; onCerrar: () => void }) {
  const [p, setP] = useState<Prospecto | null>(null);
  const [historial, setHistorial] = useState<Interaccion[]>([]);
  const [registrando, setRegistrando] = useState(false);

  const cargar = useCallback(async () => {
    const r = await api.get<{ prospecto: Prospecto; interacciones: Interaccion[] }>(`/api/captacion/prospectos/${id}`);
    setP(r.prospecto);
    setHistorial(r.interacciones);
  }, [id]);

  useEffect(() => {
    cargar().catch(() => {});
  }, [cargar]);

  async function guardar(clave: keyof Prospecto, valor: string) {
    if (!p || String(p[clave] ?? "") === valor) return;
    const numero = clave === "monto_desarrollo" || clave === "monto_mensual";
    const dato = numero ? Number(valor) : clave === "fecha_proxima_accion" ? valor || null : valor;
    await api.patch(`/api/captacion/prospectos/${p.id}`, { [clave]: dato }).catch(() => {});
    await cargar().catch(() => {});
  }

  const icono = (canal: string) => CANALES.find((c) => c.clave === canal)?.icono ?? "•";

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/40" onClick={onCerrar}>
      <aside
        className="h-full w-full max-w-md space-y-4 overflow-y-auto bg-[var(--plano)] p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        aria-label="Ficha del prospecto"
      >
        {!p ? (
          <p className="text-sm text-[var(--tinta-suave)]">Cargando…</p>
        ) : (
          <>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h2 className="text-xl font-bold">{p.empresa}</h2>
                <p className="text-sm text-[var(--tinta-2)]">
                  {[p.contacto, p.puesto].filter(Boolean).join(" · ") || "Sin contacto registrado"}
                </p>
              </div>
              <button onClick={onCerrar} className="h-10 w-10 shrink-0 text-lg text-[var(--tinta-suave)]" aria-label="Cerrar ficha">
                ✕
              </button>
            </div>

            {p.alertas.length > 0 && (
              <p className="rounded-lg border-l-4 bg-[var(--superficie)] px-3 py-2 text-sm font-medium" style={{ borderLeftColor: "var(--critico)" }}>
                🔴 {p.alertas.map((a) => TEXTO_ALERTA[a]).join(" · ")}
              </p>
            )}

            <button
              onClick={() => setRegistrando(true)}
              className="min-h-12 w-full rounded-lg bg-[var(--acento)] text-base font-semibold text-white"
            >
              + Registrar interacción
            </button>

            <div className="flex flex-wrap gap-2">
              {p.telefono && (
                <>
                  <a href={`tel:${p.telefono}`} className="min-h-10 rounded-lg border border-[var(--borde)] px-3 py-2 text-sm">📞 Llamar</a>
                  <a
                    href={`https://wa.me/${p.telefono.replace(/\D/g, "").replace(/^(\d{10})$/, "52$1")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="min-h-10 rounded-lg border border-[var(--borde)] px-3 py-2 text-sm"
                  >
                    💬 WhatsApp
                  </a>
                </>
              )}
              {p.link_drive && (
                <a href={p.link_drive} target="_blank" rel="noreferrer" className="min-h-10 rounded-lg border border-[var(--borde)] px-3 py-2 text-sm">
                  📁 Drive
                </a>
              )}
            </div>

            <section>
              <h3 className="mb-2 text-sm font-semibold">Historial ({historial.length})</h3>
              {historial.length === 0 && <p className="text-sm text-[var(--tinta-suave)]">Sin interacciones todavía.</p>}
              <ol className="max-h-64 space-y-2 overflow-y-auto">
                {historial.map((i) => (
                  <li key={i.id} className="tarjeta px-3 py-2 text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">
                        {icono(i.canal)} {i.resultado || "—"}
                      </span>
                      <span className="shrink-0 text-xs text-[var(--tinta-suave)]">
                        {fechaCorta(i.fecha.slice(0, 10))} {i.fecha.slice(11, 16)}
                      </span>
                    </div>
                    {i.nota && <p className="mt-0.5 text-xs text-[var(--tinta-2)]">{i.nota}</p>}
                  </li>
                ))}
              </ol>
            </section>
            <label className="block text-sm">
              <span className="font-semibold">Etapa</span>
              <select
                value={p.etapa}
                onChange={async (e) => {
                  if (await moverEtapa(p, e.target.value as Etapa).catch(() => false)) await cargar();
                }}
                className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-3 py-2 text-base"
              >
                {ETAPAS.map((e) => (
                  <option key={e.clave} value={e.clave}>
                    {e.texto}
                  </option>
                ))}
              </select>
              {p.etapa === "perdido" && <span className="mt-1 block text-xs text-[var(--tinta-2)]">Motivo: {p.motivo_perdida}</span>}
            </label>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <label className="block">
                <span className="font-semibold">Segmento</span>
                <select
                  value={p.segmento}
                  onChange={(e) => guardar("segmento", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-2 py-2 text-base"
                >
                  <option value="pyme">PyME</option>
                  <option value="independiente">Independiente</option>
                </select>
              </label>
              <label className="block">
                <span className="font-semibold">Servicio</span>
                <select
                  value={p.servicio}
                  onChange={(e) => guardar("servicio", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-2 py-2 text-base"
                >
                  {Object.entries(SERVICIOS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </label>
              <label className="col-span-2 block">
                <span className="font-semibold">Origen</span>
                <select
                  value={p.origen}
                  onChange={(e) => guardar("origen", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-2 py-2 text-base"
                >
                  {Object.entries(ORIGENES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="space-y-2">
              {CAMPOS.map((c) => (
                <label key={`${p.id}-${c.clave}`} className="block text-sm">
                  <span className="font-semibold">{c.texto}</span>
                  <input
                    type={c.tipo ?? "text"}
                    defaultValue={String(p[c.clave] ?? "")}
                    onBlur={(e) => guardar(c.clave, e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-3 py-2 text-base"
                  />
                </label>
              ))}
              <label className="block text-sm">
                <span className="font-semibold">Notas</span>
                <textarea
                  defaultValue={p.notas}
                  onBlur={(e) => guardar("notas", e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-lg border border-[var(--borde)] bg-[var(--superficie)] px-3 py-2 text-base"
                />
              </label>
              <p className="text-xs text-[var(--tinta-suave)]">
                {mxn(p.monto_desarrollo)} desarrollo + {mxn(p.monto_mensual)}/mes
              </p>
            </div>

            <p className="text-xs text-[var(--tinta-suave)]">
              Etapas: {Object.entries(p.fechas_etapa).map(([e, f]) => `${TEXTO_ETAPA[e as Etapa] ?? e} ${fechaCorta(f)}`).join(" → ")}
            </p>
          </>
        )}
      </aside>
      {registrando && p && (
        <RegistrarInteraccion
          prospectoId={p.id}
          empresa={p.empresa}
          onCerrar={() => setRegistrando(false)}
          onListo={() => {
            setRegistrando(false);
            cargar().catch(() => {});
          }}
        />
      )}
    </div>
  );
}
