// Etiquetas y utilidades de Captación SINPROTEK (Fase 1). Solo presentación:
// las reglas (alertas, KPIs, salud) vienen calculadas del backend.
import type { Canal, Etapa } from "../tipos";

export const ETAPAS: { clave: Etapa; texto: string; corto: string }[] = [
  { clave: "identificado", texto: "Identificado", corto: "Ident." },
  { clave: "contactado", texto: "Contactado", corto: "Contact." },
  { clave: "reunion_agendada", texto: "Reunión agendada", corto: "Reunión" },
  { clave: "demo_hecha", texto: "Demo hecha", corto: "Demo" },
  { clave: "propuesta_enviada", texto: "Propuesta enviada", corto: "Propuesta" },
  { clave: "negociacion", texto: "Negociación", corto: "Negoc." },
  { clave: "ganado", texto: "Ganado", corto: "Ganado" },
  { clave: "perdido", texto: "Perdido", corto: "Perdido" },
];
export const TEXTO_ETAPA = Object.fromEntries(ETAPAS.map((e) => [e.clave, e.texto])) as Record<Etapa, string>;

export const ORIGENES: Record<string, string> = {
  canacintra: "CANACINTRA",
  referido: "Referido",
  linkedin: "LinkedIn",
  campo: "Campo",
  llamada_alex: "Llamada Alex",
  denue: "Base DENUE",
  otro: "Otro",
};

export const SERVICIOS: Record<string, string> = {
  agente_whatsapp: "Agente WhatsApp",
  agente_voz: "Agente de voz",
  consultoria: "Consultoría",
  capacitacion: "Capacitación",
};

export const CANALES: { clave: Canal; texto: string; icono: string }[] = [
  { clave: "llamada", texto: "Llamada", icono: "📞" },
  { clave: "whatsapp", texto: "WhatsApp", icono: "💬" },
  { clave: "visita", texto: "Visita", icono: "🚶" },
  { clave: "correo", texto: "Correo", icono: "✉️" },
  { clave: "reunion", texto: "Reunión", icono: "🤝" },
  { clave: "alex", texto: "Alex", icono: "🤖" },
];

export const RESULTADOS_RAPIDOS = [
  "Contestó",
  "No contestó",
  "Interesado",
  "Agendó reunión",
  "Pidió cotización",
  "No interesado",
];

export const TEXTO_ALERTA: Record<string, string> = {
  accion_vencida: "acción vencida",
  sin_contacto: "sin contacto > 7 días",
};

const FORMATO_MXN = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
export const mxn = (n: number) => FORMATO_MXN.format(n);

/** Fecha ISO de hoy + n días, en hora local (la del navegador = Querétaro). */
export function enDias(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
