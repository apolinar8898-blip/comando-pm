# 🎯 Comando PM

App web **personal** de gestión de portafolio de proyectos basada en PMBOK.
La fuente de verdad del diseño es [CLAUDE.md](CLAUDE.md).

Responde siempre tres preguntas: **¿cómo va cada proyecto?** (semáforos + KPIs),
**¿qué hago hoy y esta semana?** (plan Ivy Lee) y **¿qué retos ponen en riesgo los objetivos?**

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
npm run dev
```

Abre http://localhost:5173. Si no hay datos, el portafolio ofrece **sembrar datos
de demostración**.

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest pruebas
```

## Decisiones registradas

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
  header `X-Token`; guarda el valor en localStorage como `comando_pm_token`.

## Estado (Fase 1 + inicio de Fase 2)

- ✅ Dominio puro con tests: salud calculada, avance ponderado, SPI (EVM
  simplificado), Eisenhower, sugerencia Ivy Lee (máx. 6), ruta crítica.
- ✅ API completa: portafolio, proyectos, tareas, retos, plan de hoy, cierre de
  día, snapshots diarios de KPIs, demo.
- ✅ Vistas: **Hoy** (Ivy Lee + semáforos + retos que arden), **Portafolio**
  (tarjetas KPI + roadmap), **Proyecto** (dashboard + Gantt + tareas).
- ⏳ Siguiente (CLAUDE.md §8): matriz Eisenhower drag & drop, plan semanal,
  documentos estratégicos (charter, canvas, SMART, Porter) y RCA con 5 porqués.
