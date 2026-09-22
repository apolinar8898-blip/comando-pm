# 🎯 Comando PM

App web **personal** de gestión de portafolio de proyectos basada en PMBOK.
La fuente de verdad del diseño es [CLAUDE.md](CLAUDE.md).

Responde siempre tres preguntas: **¿cómo va cada proyecto?** (semáforos + KPIs),
**¿qué hago hoy y esta semana?** (plan Ivy Lee) y **¿qué retos ponen en riesgo los objetivos?**

## Uso diario (un solo clic)

Doble clic en **`arrancar.ps1`** (o un acceso directo a
`powershell -ExecutionPolicy Bypass -File arrancar.ps1`): levanta un solo
proceso en http://localhost:8000 que sirve la app compilada y la API.
Requiere haber hecho la instalación inicial (abajo) y `npm run build` una vez.

## Correr en desarrollo

```powershell
# Backend (FastAPI, puerto 8000)
cd backend
python -m venv .venv          # solo la primera vez
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload

# Frontend (Vite, puerto 5173, proxy /api → 8000)
cd frontend
npm install                   # solo la primera vez
npm run dev                   # desarrollo con HMR
npm run build                 # compila dist/ para el modo "un solo clic"
```

Abre http://localhost:5173 (desarrollo) o http://localhost:8000 (compilada).
Si no hay datos, el portafolio ofrece **sembrar datos de demostración**.

## Producción (Railway + Supabase)

- Un solo servicio en Railway construido con el `Dockerfile` (compila la SPA y la
  sirve desde FastAPI). Deploy automático al hacer `git push` a GitHub.
- Variables en Railway → Service → Variables (plantilla en `.env.example`):
  `DATABASE_URL` (Session pooler de Supabase) y `APP_PASSWORD`.
- Base de datos: `schema.sql` para una DB nueva; `migraciones/NNN_*.sql` para
  una existente (en orden, desde el SQL Editor de Supabase).
- Scripts (desde `backend`, leen el `.env` de la raíz):
  - `.venv\Scripts\python scripts\migrar_json_a_supabase.py`: copia el JSON local a Supabase.
  - `.venv\Scripts\python scripts\fase0_proyectos_reales.py`: portafolio real (idempotente).

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest pruebas
```

## Decisiones registradas

- **Persistencia en producción: Supabase** (`repositorio_supabase.py`, diff por
  transacción) cuando existe `DATABASE_URL`; si no, archivo JSON. Ver CLAUDE.md §12.
- **Rutinas**: trabajo recurrente que genera la tarea real de cada día (↻ en Hoy).
- **Persistencia v1: archivo JSON** (`backend/datos/comando-pm.json`) mediante
  `repositorio.py`. `schema.sql` ya define el esquema completo para migrar a
  Supabase cambiando solo esa capa. Ruta configurable con `COMANDO_PM_DATOS`.
- **Gantt propio en SVG** (no `frappe-gantt`): control total de drag para
  reprogramar, hitos ◆, dependencias, línea de HOY y ruta crítica, sin depender
  de una librería con API cambiante.
- **Gráficas propias en SVG** con la paleta validada del sistema de dataviz
  (una serie → sin leyenda; tooltip con crosshair al pasar el mouse).
- **Estado del frontend: fetch simple + estado local de React** (sin React
  Query/Zustand): una sola usuaria/o, datos chicos, recarga tras cada mutación.
- **Seguridad mínima**: si defines `APP_PASSWORD` en el backend, la API exige el
  header `X-Token` (comparación de tiempo constante); guarda el valor en
  localStorage como `comando_pm_token`. La SPA estática se sirve sin token.
- **Persistencia blindada** (dictamen del consejo de revisión): escritura
  atómica (tmp + `os.replace`), candado por petición (los endpoints corren en
  threadpool), respaldo diario automático en `backend/datos/respaldos/`
  (retiene 30), recuperación ante archivo corrupto (se aparta y se restaura el
  último respaldo), y **botón "⬇ Respaldo"** en Portafolio que descarga todo
  (`GET /api/export`).
- **Errores visibles**: todo fallo de la API dispara un toast global; el plan
  Ivy Lee se reordena con ▲/▼; los pendientes de ayer se arrastran al frente
  de la sugerencia de hoy.

## Estado (las 4 fases del prompt maestro completas)

- ✅ Dominio puro con tests: salud calculada, avance ponderado, SPI (EVM
  simplificado), Eisenhower, sugerencia Ivy Lee (máx. 6), ruta crítica.
- ✅ API completa: portafolio, proyectos, tareas (listado expandido con
  cuadrante), retos, plan de hoy, cierre de día, snapshots diarios, demo.
- ✅ Vistas: **Hoy** (Ivy Lee + semáforos + retos que arden), **Semana**
  (tablero lun-dom con reprogramación y carril de vencidas), **Eisenhower**
  (matriz 2×2 global y por proyecto), **Portafolio** (tarjetas KPI + roadmap),
  **Proyecto** (dashboard + Gantt + semana + eisenhower + tareas).
- ✅ Drag & drop con fallback de click/touch: mover de cuadrante y reprogramar
  días funciona también sin mouse (móvil).
- ✅ Documentos estratégicos versionados (historial JSONB): charter con
  **siembra de hitos reales en el Gantt**, canvas, Porter con radar SVG,
  objetivos SMART con validación dura, fase del proyecto en el roadmap y
  vista de lectura imprimible.
- ✅ Pestaña Retos: mapa de calor impacto×probabilidad 5×5 (zonas alineadas
  con la regla de salud), CRUD de retos, y "hacer RCA" desde un reto
  materializado.
- ✅ RCA con 5 porqués ramificables (árbol de hasta 7 niveles), causa raíz
  elegida de las hojas, línea de tiempo, y **acciones correctivas + señal de
  verificación que se convierten en tareas reales** (origen_rca); la vista de
  lectura muestra el estado real de cada acción.
- ✅ Cierre de proyecto: lecciones aprendidas + archivado (nada se borra) y
  reapertura.
