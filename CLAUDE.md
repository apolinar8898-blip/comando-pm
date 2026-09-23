# Prompt maestro — "Comando PM": app personal de gestión de proyectos basada en PMBOK

> Pégalo como `CLAUDE.md` en la raíz del repo del nuevo proyecto (o como contexto en Claude).
> Es la fuente de verdad. Si algo aquí contradice al código, gana este documento hasta que lo actualicemos.

---

## 1. Rol y objetivo

Eres el ingeniero principal de **Comando PM**, una aplicación web **personal (un solo usuario)** para un Project Manager que gestiona un **portafolio de varios proyectos** a la vez. La app se apoya en el marco del **PMBOK** (grupos de procesos y áreas de conocimiento) pero sin burocracia: es una herramienta de trabajo diario, no un sistema corporativo.

La app responde en todo momento, de forma **visual y en menos de 5 segundos de lectura**, tres preguntas:

1. **¿Cómo va cada proyecto?** (salud del portafolio: semáforos, avance, KPIs)
2. **¿Qué tengo que hacer hoy y esta semana?** (plan diario Ivy Lee + plan semanal)
3. **¿Cuáles son los retos importantes que ponen en riesgo los objetivos?** (riesgos, bloqueos, hitos en peligro)

**Trabaja en español** (UI, comentarios, documentación). Usa unidades métricas y fechas en formato `dd/mm/aaaa` en la UI.

---

## 2. Decisiones de arquitectura NO negociables

- **Web app: React (Vite) + FastAPI (Python) + Supabase (Postgres).** El frontend consume una API propia en FastAPI; Supabase es la base de datos y el storage. Nada de no-code en la ruta crítica.
- **Un solo usuario.** Sin registro ni roles. Protección mínima: una variable de entorno `APP_PASSWORD` que gatea la API (login simple con token en localStorage). No construir sistema de usuarios.
- **Los documentos estratégicos viven como JSONB**, no como decenas de columnas. Charter, Canvas, Porter, RCA, etc. son documentos versionables con estructura flexible.
- **Lógica de negocio pura y testeable**: los cálculos (KPIs, semáforos, clasificación Eisenhower, ruta crítica del Gantt) son funciones puras en Python, sin efectos de red/DB dentro, con tests. El frontend solo pinta.
- **Mobile-friendly pero desktop-first.** El Gantt y el dashboard se diseñan para pantalla grande; la vista "Hoy" debe funcionar perfecta en el teléfono.
- **Sin dependencias de pago.** Librerías open source para Gantt y gráficas (por ejemplo `frappe-gantt` o un Gantt propio en SVG, y `recharts` para gráficas). Evalúa y decide, pero documenta la decisión.

---

## 3. Modelo de dominio (corazón del sistema)

### Entidades

| Entidad | Descripción | Campos clave |
|---|---|---|
| `proyecto` | Unidad del portafolio | nombre, descripción, estado (`activo/pausado/cerrado/cancelado`), fecha_inicio, fecha_fin_objetivo, salud (`verde/amarillo/rojo`, **calculada, nunca manual**), color, prioridad |
| `objetivo` | Objetivo SMART del proyecto | los 5 campos SMART explícitos: `especifico`, `medible` (métrica + valor objetivo + valor actual), `alcanzable` (justificación), `relevante` (justificación), `fecha_limite` |
| `tarea` | Trabajo ejecutable | proyecto_id, título, descripción, estado (`pendiente/en_curso/hecha/bloqueada`), fecha_inicio, fecha_fin, duración, dependencias (ids), es_hito (bool), urgente (bool), importante (bool), esfuerzo_estimado_h, esfuerzo_real_h |
| `reto` | Riesgo, bloqueo o desafío importante | proyecto_id, título, tipo (`riesgo/bloqueo/decision_pendiente`), impacto (1-5), probabilidad (1-5), plan_de_respuesta, estado (`abierto/mitigado/materializado/cerrado`) |
| `documento` | Documento estratégico versionado | proyecto_id (nullable: Porter puede ser de portafolio), tipo (`charter/canvas/porter/roadmap/rca`), contenido JSONB, versión, creado_en |
| `plan_dia` | Plan diario método Ivy Lee | fecha (única), lista ordenada de **máximo 6** tarea_ids, notas de cierre del día |
| `kpi_snapshot` | Foto diaria de KPIs por proyecto | proyecto_id, fecha, avance_pct, tareas_vencidas, spi, retos_abiertos… (para gráficas de tendencia) |

### Reglas de dominio (no negociables)

- **La salud del proyecto se calcula, no se opina.** Regla inicial: `rojo` si hay hito vencido o SPI < 0.8 o reto abierto con impacto×probabilidad ≥ 16; `amarillo` si hay tareas vencidas o SPI < 0.95 o reto ≥ 9; `verde` en otro caso. La regla vive en UNA función pura con tests.
- **Eisenhower deriva de dos booleanos** (`urgente`, `importante`) en la tarea. El cuadrante es una función, no un campo. Urgente se sugiere automáticamente si `fecha_fin ≤ hoy + 2 días`, pero el usuario puede fijarlo manualmente (flag `urgente_manual`).
- **Ivy Lee es un límite duro: 6 tareas por día, ordenadas.** La UI no permite la séptima. Al iniciar el día, la app propone las 6 a partir de: hitos próximos → cuadrante I (urgente+importante) → cuadrante II (importante). El usuario reordena/reemplaza y confirma.
- **Un hito es una tarea con `es_hito = true` y duración 0.** No crear tabla aparte.
- **Avance del proyecto** = ponderado por esfuerzo estimado de tareas hechas / total (no por conteo simple).
- **SPI simplificado** (inspirado en EVM del PMBOK): valor ganado (esfuerzo de lo hecho) / valor planificado (esfuerzo que debería estar hecho a hoy según fechas). Sin costos en v1 — es herramienta personal, el CPI queda fuera.

---

## 4. Las vistas (lo que se ve es el producto)

### 4.1 "Hoy" — pantalla de inicio (la más importante)
- **Plan Ivy Lee del día**: las 6 tareas ordenadas, con checkbox, proyecto de origen (chip de color) y cuadrante Eisenhower como etiqueta discreta.
- **Semáforo del portafolio**: una fila de tarjetas mini por proyecto activo (nombre, salud, avance %, próximo hito con fecha).
- **Retos que arden**: máximo 3, los de mayor impacto×probabilidad abiertos.
- **Ritual de cierre**: botón "Cerrar el día" → marca qué se terminó, lo pendiente se ofrece para el plan de mañana (Ivy Lee puro), y pide una nota de 1 línea.

### 4.2 Portafolio
- Tabla/tarjetas de todos los proyectos: salud, avance, SPI, hito próximo, retos abiertos, fecha fin objetivo vs proyección.
- **Roadmap de portafolio**: línea de tiempo horizontal por trimestres con las barras de todos los proyectos y sus hitos (diamantes). Es el Gantt "de 10,000 metros".

### 4.3 Proyecto (drill-down) — pestañas:
1. **Dashboard**: KPIs del proyecto (avance %, SPI, tareas vencidas, tareas de esta semana, retos abiertos, días para fin), gráfica burndown/avance vs plan (de `kpi_snapshot`), objetivos SMART con barra de progreso (valor actual/objetivo de la métrica).
2. **Gantt**: barras con dependencias, hitos como diamantes, línea de "hoy", ruta crítica resaltada, drag para mover fechas. Zoom día/semana/mes.
3. **Plan semanal**: tablero de la semana (lunes-domingo) con las tareas cuya fecha cae en la semana; arrastrar entre días reprograma.
4. **Eisenhower**: matriz 2×2 con las tareas pendientes del proyecto; arrastrar entre cuadrantes ajusta los flags. Vista también disponible a nivel portafolio (todas las tareas).
5. **Retos**: matriz impacto×probabilidad (mapa de calor 5×5) + lista con plan de respuesta.
6. **Documentos**: charter, canvas, roadmap, análisis Porter, RCAs (ver §5).

---

## 5. Documentos estratégicos (plantillas JSONB)

Cada tipo tiene un **formulario guiado** (no un editor libre) y una **vista de lectura bonita e imprimible** (export a PDF por impresión del navegador es suficiente en v1).

### 5.1 Project Charter / Acta de constitución (PMBOK)
Campos: justificación del proyecto, objetivos medibles (enlaza a los objetivos SMART), alcance (incluye / **no incluye** — explícito), entregables principales, hitos de alto nivel, supuestos, restricciones, riesgos iniciales, criterios de éxito, presupuesto estimado (opcional), interesados clave, fecha y "firma" (confirmación). **Al confirmar el charter, la app ofrece crear los hitos y objetivos SMART directamente desde él** — el charter no es papel muerto, siembra el plan.

### 5.2 Canvas de proyecto
Cuadrícula de una pantalla: propósito, entregables, hitos, requisitos/recursos, equipo/aliados (aunque sea personal: quién más participa), riesgos, restricciones, presupuesto, criterios de éxito. Es el "charter exprés" para proyectos chicos: la app pregunta al crear un proyecto si quieres charter completo o canvas.

### 5.3 Objetivos SMART
Formulario que **obliga** a llenar los 5 componentes y valida: si "medible" no tiene métrica numérica con valor objetivo, no guarda. El progreso del objetivo se actualiza editando "valor actual" y se pinta en el dashboard.

### 5.4 Análisis de las cinco fuerzas de Porter
Documento a nivel proyecto o portafolio: las 5 fuerzas (competidores, nuevos entrantes, sustitutos, poder de proveedores, poder de clientes), cada una con intensidad (1-5) + notas. Vista: diagrama de araña/radar + resumen. Es un documento de contexto estratégico, no operativo: sin lógica adicional.

### 5.5 Roadmap
No es documento aparte: es la vista de portafolio (§4.2) filtrable + anotaciones de fase por proyecto (`fase`: texto + rango de fechas, ej. "Descubrimiento", "Construcción", "Lanzamiento"). Exportable/imprimible.

### 5.6 Análisis causa raíz (RCA) — plantilla de mejora continua ⭐
El foco: **saber qué pasó y cómo evitar que se repita.** Formulario guiado:
1. **¿Qué pasó?** (hecho, no interpretación: qué, cuándo, dónde, impacto medible)
2. **Línea de tiempo** (lista de eventos con fecha/hora)
3. **5 porqués**: cadena guiada — la app pide el porqué de cada respuesta anterior, mínimo 3, máximo 7 niveles; permite ramificar (un porqué puede tener dos causas)
4. **Causa raíz identificada** (se elige de las hojas de la cadena de porqués)
5. **Acciones correctivas** — cada una se convierte en **tarea real** en un proyecto (con responsable implícito: tú, y fecha), para que el aprendizaje no se quede en el documento
6. **¿Cómo sabremos que no volvió a pasar?** (señal de verificación + fecha de revisión — la app crea una tarea de verificación futura automáticamente)

Un RCA puede nacer desde un reto materializado (botón "hacer RCA" en el reto) o suelto. Vista de lectura: diagrama de la cadena de porqués + tabla de acciones con su estado real (leído de las tareas).

---

## 6. Alineación PMBOK (marco, no burocracia)

Mapa mental que guía el diseño — no crear módulos por área de conocimiento:

- **Inicio** → Charter / Canvas
- **Planificación** → objetivos SMART, tareas, Gantt, roadmap, retos (riesgos)
- **Ejecución** → vista Hoy, plan semanal, Ivy Lee, Eisenhower
- **Monitoreo y control** → dashboard KPI, semáforos, SPI, snapshots
- **Cierre** → cerrar proyecto pide: lecciones aprendidas (mini-RCA opcional de "qué haría diferente"), estado final de objetivos SMART, y archiva el proyecto (no lo borra)

---

## 7. Stack técnico (decidido)

- **Frontend:** React + Vite + TypeScript. Estado con Zustand o React Query (decide y documenta). Estilos con Tailwind. Gráficas con Recharts. Gantt: evaluar `frappe-gantt` vs SVG propio (el drag de dependencias es lo difícil; si la librería lo resuelve, úsala).
- **Backend:** FastAPI (Python 3.12+), Pydantic v2 para contratos. La lógica de dominio (KPIs, salud, Eisenhower, ruta crítica, sugerencia Ivy Lee) en un paquete `dominio/` puro con tests pytest.
- **DB:** Supabase (Postgres) vía PostgREST o SQLAlchemy directo (decide y documenta). `schema.sql` versionado en el repo. **Fallback en memoria** para desarrollar sin credenciales (mismo patrón que proyectos previos del usuario).
- **Deploy v1:** frontend en Vercel/Netlify, API en Railway/Render o incluso local. No sobre-ingeniar: es una herramienta personal.

---

## 8. Fases de construcción, en orden estricto

**Regla de oro: cada fase termina con un hito validable usándola de verdad.** No empezar la siguiente sin validar la anterior.

### Fase 1 — El núcleo que ya sirve (proyectos + tareas + Gantt + dashboard)
1. `schema.sql` completo (todas las entidades de §3, aunque las vistas lleguen después).
2. API CRUD de proyectos y tareas + paquete `dominio/` con salud, avance y SPI (con tests).
3. Vista Portafolio (semáforos) y vista Proyecto con Dashboard + Gantt.
4. Snapshot diario de KPIs (cron simple o al primer acceso del día).

> **Hito F1:** cargar 2 proyectos reales tuyos con sus tareas y que el Gantt y los semáforos digan la verdad. Si el semáforo miente, arreglar la regla antes de seguir.

### Fase 2 — El plan de cada día (la razón de ser de la app)
5. Vista "Hoy" con plan Ivy Lee (sugerencia automática + edición + límite de 6).
6. Ritual de cierre del día y arrastre de pendientes a mañana.
7. Matriz Eisenhower (proyecto y portafolio) con drag & drop.
8. Plan semanal con drag entre días.

> **Hito F2:** usar la app como planificador diario real durante 5 días seguidos. Lo que estorbe del ritual, se corrige.

### Fase 3 — Documentos estratégicos
9. Motor de documentos JSONB versionados + vista de lectura imprimible.
10. Charter (con siembra de hitos/objetivos) y Canvas.
11. Objetivos SMART con validación dura y progreso en dashboard.
12. Porter (radar) y anotaciones de fase para el Roadmap.

> **Hito F3:** hacer el charter real de un proyecto nuevo desde la app y que siembre su plan.

### Fase 4 — Mejora continua y retos
13. Módulo de retos con matriz impacto×probabilidad y efecto en la salud.
14. RCA completo con 5 porqués ramificables y acciones que crean tareas reales.
15. Flujo de cierre de proyecto con lecciones aprendidas.

> **Hito F4:** documentar con RCA un problema real pasado, con sus 5 porqués y al menos 2 acciones correctivas convertidas en tareas con fecha.

---

## 9. Restricciones y trampas (léelas antes de codear)

- **La vista "Hoy" es el producto.** Si hay que sacrificar algo por tiempo, se sacrifica cualquier cosa menos Hoy, Gantt y semáforos.
- **No inflar el PMBOK.** Nada de gestión de adquisiciones, comunicaciones formales ni EVM completo. Un usuario, herramienta diaria: cada campo que se pide al usuario debe ganarse su lugar.
- **Semáforos calculados, jamás manuales.** Un semáforo editable a mano se convierte en decoración en una semana.
- **Ivy Lee sin trampas:** 6 es 6. Si el usuario quiere 10 tareas hoy, el problema es de priorización y la app debe hacerlo visible, no ceder.
- **El RCA debe terminar en tareas**, no en un PDF que nadie relee. La señal de verificación futura con tarea automática es obligatoria.
- **Nada se borra, se archiva.** Proyectos cerrados y documentos viejos quedan consultables (las lecciones aprendidas valen oro después).
- **Rendimiento del Gantt:** con 200+ tareas debe seguir fluido; virtualizar o paginar por proyecto si hace falta.
- **Backups:** export completo a JSON con un botón (es tu portafolio de trabajo; sin backup no hay confianza).

---

## 10. Convenciones de código

- Español en UI, mensajes, comentarios y documentación. Código (variables/funciones) en español consistente.
- Lógica de dominio pura, sin red/DB, con tests pytest; cada regla de §3 tiene su test.
- El frontend no calcula reglas de negocio: pide a la API. Excepción: interacciones de UI (drag) con confirmación optimista.
- `schema.sql` es la fuente de verdad de la DB, versionado en el repo con migraciones numeradas.
- Antes de escribir un módulo nuevo, revisa qué ya existe para reutilizar.
- Cada fase nueva incluye una simulación o test e2e ligero de su flujo principal.

---

## 11. Estado actual (julio 2026)

**Fases 1, 2 y 3 construidas y verificadas end-to-end:**

- Fase 1: dominio puro con tests (salud calculada, avance ponderado, SPI,
  Eisenhower, Ivy Lee, ruta crítica), API FastAPI, repositorio con
  persistencia a archivo (migración a Supabase = solo esa capa), vistas
  Hoy / Portafolio / Proyecto (dashboard + Gantt SVG propio).
- Fase 2: matriz Eisenhower 2×2 y plan semanal, con drag & drop y fallback
  de click/touch, a nivel portafolio y como pestañas del proyecto.
- Fase 3: documentos JSONB versionados con historial (charter, canvas,
  Porter con radar SVG), charter que siembra hitos reales en el Gantt,
  objetivos SMART con validación dura, fase del proyecto en el roadmap,
  vista de lectura imprimible.

- Fase 4: pestaña Retos con mapa de calor impacto×probabilidad 5×5 y
  "hacer RCA" desde retos materializados; RCA con 5 porqués ramificables,
  causa raíz, y acciones + verificación futura que se convierten en tareas
  reales (origen_rca) con estado visible; cierre de proyecto con lecciones
  aprendidas y archivado.

**Las 4 fases del §8 están completas.** Siguientes pasos naturales (no
comprometidos): export JSON de respaldo, migración del repositorio a
Supabase, despliegue (Vercel + Railway) y protección con APP_PASSWORD.

---

## 12. Centro de mando personal y profesional (desde 22/09/2026)

Comando PM deja de ser un demo PMBOK y se vuelve el centro de mando de Apo
Ramírez Villalón (Querétaro). **Todo lo que se construya debe ayudar a cerrar
clientes SINPROTEK, cerrar operaciones REMAX o cumplir el plan de IRONMAN.**
Unidades SI, formato 24 h, MXN, interfaz en español.

### Frentes y metas
- **SINPROTEK / PropIA** (agentes de IA por WhatsApp y voz "Alex"). **Meta que
  gobierna todo: 3 clientes pagando antes del 31/12/2026.** Clúster: CANACINTRA
  Querétaro. Precios: PyME $4,000 + $4,000/mes; independiente $3,000 + $3,500/mes.
- **REMAX Infinity**: 1 captación, 1 venta y 1 renta por mes. Comisión: 50 %
  REMAX, 25 % captador, 25 % quien trae comprador.
- **IRONMAN 70.3 Campeche, 08/11/2026.** Peso objetivo el día de la carrera: 86 kg.
- **Apo Villalón** (marca personal LinkedIn/YouTube que alimenta SINPROTEK).
- Uber (ingreso actual; SAT mensual el día 17).
- Zenzontle: **cancelado** el 22/09/2026 (queda en historial).

### Fases del centro de mando (una a la vez; cada una cierra con tests en verde,
prueba local, despliegue y actualización de este documento)
- **Fase 0 — Limpieza y despliegue** ✅ código listo (ver abajo).
- **Fase 1 — Captación SINPROTEK** ✅ (CRM de prospectos, kanban, KPIs en
  `dominio/captacion.py`, endpoint para Alex/VAPI; ver "Decisiones de la Fase 1"). Al cerrarla: recordar a Apo
  registrar **5 días seguidos de Ivy Lee antes de empezar la Fase 2**.
- **Fase 2 — Dashboard REMAX** (propiedades, operaciones, embudo SVG).
- **Fase 3 — Integraciones** (Google Calendar, Strava, Drive). Notion NO.
- **Fase 4 — Ingresos y obligaciones** (ingresos por fuente, recordatorio SAT).

### Decisiones de la Fase 0
- **Rutinas** (`dominio/rutinas.py`, tabla `rutinas`): el trabajo recurrente
  (entrenos, prospección diaria, post diario) NO se pre-crea como cientos de
  tareas. Cada día que toca, la API materializa UNA tarea real (`rutina_id`)
  al primer acceso (`_materializar_rutinas`), también los días en que no se
  abrió la app (máx. 31 hacia atrás, nunca a futuro). Una instancia de un día
  pasado sin hacer **expira**: no cuenta como vencida ni se sugiere en Ivy Lee,
  pero sí pesa en el SPI (el SPI mide la adherencia al plan). Nada se borra:
  una rutina se pausa (`activa = false`). El Gantt no muestra instancias de rutina.
- **"Hoy" es el de Querétaro** (`app/reloj.py`, `ZONA_HORARIA`, por defecto
  America/Mexico_City). Railway corre en UTC; `date.today()` está prohibido en la API.
- **Persistencia en producción: Supabase** con `RepositorioSupabase`
  (`repositorio_supabase.py`, psycopg 3 directo, no PostgREST). Carga todo a
  memoria al arrancar; cada `guardar()` escribe solo el diff en UNA transacción
  (si falla, el siguiente guardar reintenta). `crear_repositorio()` elige
  Supabase si existe `DATABASE_URL`; si no, el JSON de siempre (tests y respaldo).
  `DATABASE_URL` = **Session pooler** de Supabase (la conexión directa es solo IPv6).
- **RLS activado sin políticas** en todas las tablas: cierra la API pública de
  Supabase; el backend entra como `postgres` y no le afecta.
- **Migraciones numeradas** en `migraciones/` (tabla `migraciones` registra las
  aplicadas). `schema.sql` = estado completo acumulado para una DB nueva.
- **Despliegue: Railway, un solo servicio** con `Dockerfile` de dos etapas (Node
  compila la SPA → Python la sirve con uvicorn en `$PORT`). Healthcheck público
  `GET /api/ping` (sin datos). Deploy automático desde GitHub.
- **Login**: si la API responde 401, la SPA muestra la pantalla de contraseña
  (`APP_PASSWORD`) y guarda el token en localStorage (`comando_pm_token`).
- **Vista Hoy móvil primero** (380 px): tareas a 16 px con título completo (sin
  truncar), checkbox de 28 px con toda la fila como blanco táctil, botones de
  ≥ 44 px, semáforos en 2 columnas (solo icono en celular), sin scroll lateral.
- **Portafolio real** cargado por `app/semilla_real.py` (idempotente, con test):
  demos CTWA y CRM → `cerrado`; Zenzontle → `cancelado`; SINPROTEK, REMAX,
  IRONMAN y Apo Villalón con objetivos SMART, hitos y rutinas. En días hábiles
  4 de los 6 lugares de Ivy Lee son rutinas: es la realidad del plan, no se esconde.

### Variables de entorno (ver `.env.example`; nunca en código)
`DATABASE_URL`, `APP_PASSWORD`, `ZONA_HORARIA` (opcional), `COMANDO_PM_DATOS` (opcional, solo JSON).

### Estado de la Fase 0 (22/09/2026)
Desplegada en **https://comando-pm-production.up.railway.app** (Railway, US West,
deploy automático desde `main` de github.com/apolinar8898-blip/comando-pm).
Supabase con migraciones 001–003; datos del JSON migrados y portafolio real cargado.
Lecciones del despliegue:
- Variable `PORT=8080` en Railway, igual al puerto del dominio público.
- La URI de Supabase trae `?pgbouncer=true` (formato Prisma): `limpiar_dsn` lo quita.
- Al pegar la contraseña en la URI NO dejar los corchetes de `[YOUR-PASSWORD]`.
  Varios intentos fallidos activan `ECIRCUITBREAKER` en Supabase (bloqueo temporal);
  por eso la app espera `ESPERA_REINTENTO_DB` (60 s) antes de caer si no conecta.
- Cambios de variables en Railway quedan "en espera" hasta dar Deploy.

### Decisiones de la Fase 1 — Captación SINPROTEK (22/09/2026)
- Tablas `prospectos`, `interacciones`, `configuracion` (migración 004). Valores
  con `check` sobre texto, no enums: agregar un origen es una línea de SQL.
- **`fechas_etapa`** (jsonb) guarda la primera entrada a cada etapa: la conversión
  etapa a etapa usa la etapa MÁS ALTA alcanzada (un perdido tras la demo sí cuenta
  como que llegó a demo). "Perdido" exige motivo (modelo + check en DB).
- Montos precargados por segmento (PyME 4,000 + 4,000/mes; independiente 3,000 +
  3,500/mes), editables. MRR ponderado = mensualidad × probabilidad de la etapa
  (5/10/20/35/50/70 %, en `configuracion.probabilidad_etapa`).
- **Alertas 🔴**: próxima acción vencida, o > 7 días sin interacción (sin
  interacciones cuenta desde el alta). Cerrados no alertan.
- **Ritmo semanal prorrateado** como el SPI: interacciones lun–hoy vs meta × días
  hábiles COMPLETADOS / 5. El lunes no se evalúa (no amanece en rojo).
  Meta configurable (`meta_interacciones_semana`, 25 = 5 × día hábil).
- **Salud de SINPROTEK** = peor(regla normal, regla de captación): 🔴 si > 3
  prospectos sin contacto > 7 días o ritmo < 50 %. El proyecto de captación se
  identifica por `configuracion.proyecto_captacion_id` o nombre "SINPROTEK…".
- **Objetivo SMART "clientes pagando" se calcula** (= prospectos ganados); no se
  captura a mano (`ServicioCaptacion.sincronizar_objetivo`).
- **Próxima acción → tarea real** (`tareas.prospecto_id`, a lo más una abierta por
  prospecto; es una proyección: si el prospecto se cierra o queda sin fecha, se
  quita). **Ivy Lee**: acciones de prospección vencidas o de hoy van ANTES que todo
  (`componer_plan`), incluso sobre los pendientes de ayer; tope configurable
  `tope_prospeccion_ivy` (Apo eligió 6: pueden llenar el día).
- Registrar interacción (2 toques: abrir + resultado; canal y "seguimiento en 3
  días" preseleccionados) cierra la acción abierta, agenda la siguiente y mueve
  "identificado" → "contactado". En Hoy, el checkbox de una acción de prospección
  abre "Registrar" en vez de solo tacharla.
- **Alex (VAPI)**: `POST /api/captacion/alex`, router aparte con token propio
  `ALEX_TOKEN` (header `Authorization: Bearer …`), NO usa APP_PASSWORD. Acepta el
  formato `tool-calls` de VAPI (`message.toolCallList[].function.arguments`) o JSON
  plano; responde `{"results": [{"toolCallId", "result"}]}`. Empata prospecto por
  los últimos 10 dígitos del teléfono (o el número del que llama); si no existe
  lo crea (origen llamada_alex). `agendo_cita` → etapa "reunión agendada" y
  próxima acción en `fecha_cita`; si no, seguimiento en 2 días.
- **Hora local también para datetimes** (`reloj.ahora_local`): en Railway
  `datetime.now()` es UTC y descuadraba "esta semana" y "7 días sin contacto".
- `scripts/aplicar_migraciones.py` aplica las migraciones pendientes (lee la tabla
  `migraciones`); ya no hay que pegar SQL a mano.
- Variables nuevas: `ALEX_TOKEN`.

**Recordatorio obligatorio antes de la Fase 2:** Apo debe registrar 5 días
seguidos de Ivy Lee (cerrar el día con nota) antes de empezar el dashboard REMAX.

### Fase 2 — Dashboard REMAX: decisiones tomadas (22/09/2026, aún sin programar)
- Tablas `propiedades` y `operaciones` (migración 005, ver diagnóstico). Estatus
  "cerrada" se CALCULA (propiedad con operación ligada); no se captura.
- `mi_comision` se calcula: comisión total × 25 % (captador o comprador) o × 50 % (ambos).
- **`fecha_cobro`** en operaciones: "comisión cobrada" cuenta en el periodo del cobro.
- **Rentas**: precio = renta mensual; la comisión total se precarga como **1 mes de
  renta** (= precio de cierre), editable.
- Hitos mensuales y los 3 objetivos SMART de REMAX se actualizan solos con los datos.
- Semilla: terreno 200 m² en Bolaños, $680,000 MXN, venta, propietario Fernando
  Galván, captado sin exclusiva; **prospección y captación: 05/09/2026**.
- Condición de Apo: programar tras 5 días seguidos de Ivy Lee cerrados (día 1 = 22/09).
