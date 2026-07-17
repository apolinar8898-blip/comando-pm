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
  fecha_limite: string;
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

export interface DetalleProyecto {
  proyecto: Proyecto;
  kpis: Kpis;
  tareas: Tarea[];
  ruta_critica: string[];
  retos: Reto[];
  objetivos: Objetivo[];
  snapshots: Snapshot[];
}
