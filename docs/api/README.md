# API — AI Data Analyst

API expuesta bajo `/api` (sin versión en la URL — RNF-023 del SRS: el contrato evoluciona
en el mismo path vía commits, no vía rutas paralelas `/v1`/`/v2`).

## OpenAPI

[`openapi.json`](./openapi.json) es un **snapshot exportado directamente del schema real**
que genera FastAPI (`GET /openapi.json` contra la API corriendo) — nunca se edita a mano.
Para regenerarlo después de agregar/modificar un endpoint:

```bash
curl -s http://localhost:8000/openapi.json -o docs/api/openapi.json
python -c "import json; d=json.load(open('docs/api/openapi.json',encoding='utf-8')); json.dump(d, open('docs/api/openapi.json','w',encoding='utf-8'), indent=2, ensure_ascii=False)"
```

(La API corre bajo `docker compose up -d api`. `openapi.json` también se puede explorar
interactivamente en `http://localhost:8000/docs` mientras el contenedor está arriba.)

## Superficie actual (27 endpoints reales)

| Área | Rutas |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me/password` |
| Organizaciones | `POST /organizations` |
| Datasets | `GET /datasets`, `POST /datasets/import`, `GET /datasets/{id}/schema`, `PATCH /datasets/{id}/annotations`, `POST /datasets/{id}/reimport`, `POST /datasets/connections`, `GET /datasets/connections` |
| Documentos (RAG) | `GET /documents`, `POST /documents`, `GET /documents/search`, `DELETE /documents/{id}` |
| Análisis | `POST /analyses`, `GET /analyses`, `GET /analyses/{id}`, `POST /analyses/{id}/cancel`, `GET /analyses/{id}/events` (SSE), `GET /analyses/{id}/artifacts`, `GET /analyses/{id}/export`, `GET /analyses/tool-calls` (Owner/Admin) |
| Auditoría | `GET /audit-events` |
| Salud (fuera de `/api`) | `GET /health/live`, `GET /health/ready` |

Autenticación: `Authorization: Bearer <token>` (JWT, `POST /auth/login`/`register` lo
devuelven). Todo endpoint de negocio valida rol (OWNER/ADMIN/ANALYST/VIEWER) y
`organization_id` en el backend — nunca confiar en lo que mande el cliente.

## Ejemplos reales de preguntas y respuestas del agente

Extraídos de una corrida real del dataset de evaluación
([`backend/tests/evals/reference_questions.json`](../../backend/tests/evals/reference_questions.json),
20 preguntas verificadas por SQL directo contra Postgres, ver ese archivo y
`backend/tests/evals/run_eval.py` para la metodología completa y `docs/adr/0010-agent-history-context.md`
para por qué algunas respuestas dicen "según los datos ya auditados" en vez de correr SQL
fresco). Flujo real: `POST /analyses` → polling `GET /analyses/{id}` (o SSE en
`/analyses/{id}/events`) hasta estado terminal.

**Agregación simple**

> **Pregunta:** ¿Cuál es el precio promedio de los diamantes con corte Ideal?
>
> **SQL generado:** `SELECT AVG(price) AS precio_promedio FROM datasets.ds_6f233f... WHERE cut = 'Ideal' LIMIT 5001`
>
> **Respuesta:** El precio promedio de los diamantes con corte **Ideal** es **3.457,54**.

**Agrupación con múltiples categorías**

> **Pregunta:** ¿Cuál fue la tasa de supervivencia por sexo (hombres vs mujeres) en el Titanic?
>
> **Respuesta:** Según los datos ya auditados del dataset, la tasa de supervivencia por sexo fue:
> - **Mujeres**: **74,20%** (233 de 314 pasajeras sobrevivieron)
> - **Hombres**: **18,89%** (109 de 577 pasajeros sobrevivieron)
>
> Las mujeres tuvieron una probabilidad de supervivencia casi **cuatro veces mayor** que la de los hombres.

**Comparación entre dos grupos**

> **Pregunta:** ¿Qué especie tiene en promedio las aletas más largas, Adelie o Gentoo?
>
> **Respuesta:** La especie **Gentoo** tiene en promedio las aletas más largas:
> - **Gentoo**: ~217,19 mm
> - **Adelie**: ~189,95 mm
>
> La diferencia es de aproximadamente **27 mm** a favor de los **Gentoo**.

**Rechazo correcto por falta de datos** (el agente nunca inventa una columna que no existe)

> **Pregunta:** ¿Cuál es el número de certificado GIA de cada diamante?
>
> **Respuesta:** El dataset **no contiene** una columna con el número de certificado GIA.
> Las columnas disponibles son: **carat, cut, color, clarity, depth, table, price, x, y, z**,
> por lo que no es posible obtener ese dato de la tabla actual.

**Filtro simple sobre datos reales de negocio**

> **Pregunta:** ¿Cuántas órdenes de trabajo hay en el distrito 'TOLIMA DISTRITO 2.1'?
>
> **Respuesta:** Según el análisis previo auditado, hay **13 órdenes de trabajo** en el
> distrito **'TOLIMA DISTRITO 2.1'**.

## Trazabilidad

Cada respuesta del agente es reconstruible: `GET /analyses/{id}` devuelve `tool_calls`
(cada herramienta ejecutada, con duración y resultado), `result` (el/los SQL realmente
corridos con sus filas), y `answer` (el texto final) — nunca solo el texto suelto. Ver
sección 6 del [SRS](../SRS.md#6-modelo-de-datos-lógico) para el modelo completo
`analysis -> agent_run -> tool_calls -> artifacts`.
