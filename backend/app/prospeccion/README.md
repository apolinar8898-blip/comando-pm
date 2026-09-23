# Prospección — base de PyMEs de Querétaro

La base es el **universo** de empresas a las que SINPROTEK puede venderles:
qué empresas hay, cuánto se parecen al cliente ideal y cómo contactarlas.
El **seguimiento** (llamadas, citas, Alex, Ivy Lee) vive en el CRM de
Captación (`prospectos`): cuando una empresa se contacta pasa al CRM y
`pq_empresas.prospecto_id` guarda el vínculo. No hay un segundo embudo.

Costo: **$0**. Fuentes actuales:

| Fuente | Qué aporta | Cómo se carga |
|---|---|---|
| DENUE (INEGI), descarga masiva, entidad 22 | Base principal: nombre, giro SCIAN, tamaño, teléfono, correo, web y ubicación | `cargar_denue` (sin token ni cuota) |
| Directorio del Parque Industrial Querétaro 2024 (PDF público) | Marca `piq_2024` en empresas industriales | `importar_piq` |

## Correr todo desde cero (Windows, PowerShell)

Requisitos: haber seguido el README principal (tener `backend\.venv` y el `.env`
de la raíz con `DATABASE_URL` de Supabase).

```powershell
cd D:\ClaudIA\ComandoPM\backend
.\.venv\Scripts\python -m pip install -r requirements.txt   # rapidfuzz y pdfplumber
.\.venv\Scripts\python scripts\aplicar_migraciones.py        # crea las tablas pq_* (migración 005)
.\.venv\Scripts\python -m app.prospeccion.cargar_denue       # ~13 mil empresas, < 1 min
.\.venv\Scripts\python -m app.prospeccion.importar_piq       # cruza el directorio del PIQ
```

- `cargar_denue --simular` muestra el resumen sin escribir nada.
- `cargar_denue --zip ruta.zip` usa un zip ya descargado. Las descargas se
  guardan en `backend\datos\prospeccion\`, que no se sube a git.
- Cuando INEGI publique una edición nueva del DENUE (una vez al año), vuelve a
  correr `cargar_denue`. Actualiza lo que viene del DENUE y conserva tu
  información: score, vínculo con el CRM, opt_out y datos enriquecidos. Si una
  empresa ya no aparece, se marca `vigente = false` en lugar de borrarse.

## Qué entra a la base

- **Tamaño:** de 6 a 250 personas ocupadas. `segmento = 'nucleo'` va de 11 a 250 y
  `'micro_plus'` de 6 a 10. Se excluyen las de 0–5 y las de más de 250.
- **Se excluyen:**
  - Sector SCIAN 93: gobierno y organismos internacionales.
  - Todo lo que el DENUE marca **"del sector público"**: escuelas y clínicas públicas.
  - Para incluirlas, cambia `EXCLUIR_SECTOR_PUBLICO` en `app/dominio/prospeccion.py`.
- **Asociaciones (SCIAN 813):** entran, marcadas con `es_asociacion`.
- **Duplicados:** son la misma empresa las filas con el mismo teléfono, el mismo
  dominio propio, o la misma razón social en la misma calle. Las sucursales
  quedan bajo un solo `empresa_id` y cada una conserva su fila en
  `pq_establecimientos`. Las cadenas (Walmart, Starbucks, bancos) quedan como
  una empresa con muchas sucursales (`num_establecimientos`).
- **Teléfonos:** en formato E.164 (`+52` + 10 dígitos). `parece_celular` queda
  vacío porque, desde 2019, en México el número no dice si es fijo o móvil (ver `IDEAS.md`).
- **Dominio:** se toma del sitio web o del correo, ignorando los correos
  gratuitos (gmail, hotmail, outlook, yahoo, prodigy…).

## Tablas (migración 005)

| Tabla | Para qué |
|---|---|
| `pq_empresas` | Una fila por empresa: giro, tamaño, municipio, contacto principal, marcas (`afiliado_canacintra`, `directorios`), score/tier (Fase 3), `prospecto_id` (CRM), `opt_out` |
| `pq_establecimientos` | Cada sucursal del DENUE con dirección y coordenadas |
| `pq_contactos` | Personas (decisores) con `fuente_contacto`: denue, web, apollo, manual o directorio |
| `pq_directorio` | Registros de directorios externos y su empate. Las de `estado = 'pendiente'` forman la cola de revisión manual |
| `pq_consumo_api` | Créditos gastados por proveedor, para no pasarse de los planes gratis |

## Empate con directorios

1. **Teléfono exacto:** confianza 100.
2. **Nombre o razón social** (rapidfuzz), sin sufijos societarios (S.A. de C.V.…)
   ni palabras genéricas (Querétaro, México, Grupo…):
   - ≥ 90: `empatado`
   - 75–89: `pendiente`, para revisión manual
   - menos de 75: `sin_match`

Re-correr un importador es seguro: lo `empatado` y lo `descartado` se conservan.

## Cumplimiento

- Solo datos de contacto de **negocios**, de fuentes públicas. Cada dato
  guarda su fuente (`fuente_telefono`, `fuente_correo`, `fuente_contacto`).
- `opt_out = true` en la empresa o el contacto: nunca se exporta ni se llama.
- Sin scraping que evada logins, captchas o bloqueos.

## Fases

- [x] **Fase 0** — Tablas, `.env.example`, consumo de API.
- [x] **Fase 1** — DENUE (+ directorio PIQ).
- [ ] **Fase 2** — CANACINTRA: importador de CSV/Excel/PDF + plantilla (no hay directorio público) y SIEM.
- [ ] **Fase 3** — Score 0–100 explicable (`scoring.yaml`), tiers y la primera lista de llamadas.
- [ ] **Fase 4** — Enriquecimiento con Tavily y Apollo, con presupuesto de créditos.
- [ ] **Fase 5/6** — Endpoints, vista en el dashboard, "Pasar al CRM" y export para Alex.
