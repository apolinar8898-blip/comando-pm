// Contratos con la API (espejo de backend/app/modelos.py)

export type Salud = "verde" | "amarillo" | "rojo";
export type EstadoTarea = "pendiente" | "en_curso" | "hecha" | "bloqueada";

export interface Kpis {
  salud: Salud;
  avance_pct: number;
  spi: number;
  tareas_vencidas: number;
  retos_abiertos: number;
  proximo_hito: { id: string; titulo: string; fecha: string } | null;
  dias_para_fin: number;
}

export interface Proyecto {
  id: string;
  nombre: string;
  descripcion: string;
  estado: "activo" | "pausado" | "cerrado" | "cancelado";
  fecha_inicio: string;
  fecha_fin_objetivo: string;
  color: string;
  prioridad: number;
  fase: string;
  fase_inicio?: string | null;
  fase_fin?: string | null;
  lecciones?: string;
  kpis?: Kpis;
}

export interface Tarea {
  id: string;
  proyecto_id: string;
  titulo: string;
  descripcion: string;
  estado: EstadoTarea;
  fecha_inicio: string;
  fecha_fin: string;
  es_hito: boolean;
  importante: boolean;
  urgente_manual: boolean | null;
  dependencias: string[];
  esfuerzo_estimado_h: number;
  origen_rca?: string | null;
  rutina_id?: string | null;
  expirada?: boolean; // instancia de rutina de un día pasado sin hacer
  prospecto_id?: string | null; // próxima acción de un prospecto de SINPROTEK
  cuadrante: 1 | 2 | 3 | 4;
  proyecto_nombre: string;
  proyecto_color: string;
}

export interface Reto {
  id: string;
  proyecto_id: string;
  titulo: string;
  tipo: string;
  impacto: number;
  probabilidad: number;
  plan_de_respuesta: string;
  estado: string;
  proyecto_nombre?: string;
  puntaje?: number;
}

export interface Objetivo {
  id: string;
  especifico: string;
  metrica: string;
  valor_objetivo: number;
  valor_actual: number;
  alcanzable: string;
  relevante: string;
  fecha_limite: string;
}

export type TipoDocumento = "charter" | "canvas" | "porter" | "roadmap" | "rca";

export interface Documento {
  id: string;
  proyecto_id: string | null;
  tipo: TipoDocumento;
  version: number;
  contenido: Record<string, any>;
  historial: { version: number; contenido: Record<string, any>; fecha: string }[];
  creado_en: string;
}

export interface Snapshot {
  fecha: string;
  avance_pct: number;
  spi: number;
  salud: Salud;
}

export interface Hoy {
  fecha: string;
  cerrado: boolean;
  nota_cierre: string;
  tareas: Tarea[];
  candidatas: Tarea[];
  retos_arden: Reto[];
}

export interface Rutina {
  id: string;
  proyecto_id: string;
  titulo: string;
  dias_semana: number[]; // 0 = lunes … 6 = domingo
  importante: boolean;
  esfuerzo_estimado_h: number;
  desde: string;
  hasta: string | null;
  activa: boolean;
}

export interface DetalleProyecto {
  proyecto: Proyecto;
  kpis: Kpis;
  tareas: Tarea[];
  ruta_critica: string[];
  retos: Reto[];
  objetivos: Objetivo[];
  snapshots: Snapshot[];
  rutinas: Rutina[];
}

// ---------- Captación SINPROTEK (Fase 1) ----------

export type Etapa =
  | "identificado" | "contactado" | "reunion_agendada" | "demo_hecha"
  | "propuesta_enviada" | "negociacion" | "ganado" | "perdido";
export type Canal = "llamada" | "whatsapp" | "visita" | "correo" | "reunion" | "alex";

export interface Prospecto {
  id: string;
  empresa: string;
  contacto: string;
  puesto: string;
  telefono: string;
  correo: string;
  giro: string;
  origen: string;
  segmento: "pyme" | "independiente";
  servicio: string;
  etapa: Etapa;
  fechas_etapa: Record<string, string>;
  fecha_proxima_accion: string | null;
  proxima_accion: string;
  monto_desarrollo: number;
  monto_mensual: number;
  motivo_perdida: string;
  link_drive: string;
  notas: string;
  alertas: ("accion_vencida" | "sin_contacto")[];
  ultimo_contacto: string;
  dias_sin_contacto: number;
  num_interacciones: number;
}

export interface Interaccion {
  id: string;
  prospecto_id: string;
  fecha: string;
  canal: Canal;
  resultado: string;
  nota: string;
}

export interface KpisCaptacion {
  ganados: number;
  meta_clientes: number;
  dias_restantes: number;
  mrr_actual: number;
  mrr_ponderado: number;
  por_etapa: Record<Etapa, number>;
  conversion: { de: Etapa; a: Etapa; llegaron: number; pasaron: number; pct: number | null }[];
  interacciones_semana: number;
  meta_semana: number;
  ritmo: number | null;
  con_alerta: number;
  sin_contacto: number;
  acciones_vencidas: number;
}

export interface TableroCaptacion {
  kpis: KpisCaptacion;
  prospectos: Prospecto[];
  embudo: Etapa[];
  config: { meta_interacciones_semana: number; probabilidad_etapa: Record<string, number>; tope_prospeccion_ivy: number };
}
