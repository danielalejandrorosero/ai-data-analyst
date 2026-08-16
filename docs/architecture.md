# Arquitectura — AI Data Analyst

> Este documento describe **cómo** se construye el sistema descrito en [`SRS.md`](./SRS.md).
> El **qué** debe hacer el sistema vive en el SRS. El **por qué** de decisiones técnicas
> individuales vive en [`adr/`](./adr/). Si una afirmación aquí contradice al SRS, el SRS manda.

## 1. Visión general

Monolito modular en Python, siguiendo la arquitectura de referencia del SRS (sección 5):

- **`frontend/`** — React + TypeScript + Vite. Consume la API vía HTTPS y el stream de eventos vía SSE.
- **`backend/`** — FastAPI + Pydantic v2. Expone `/api/v1`, gestiona auth/RBAC/tenant scoping,
  valida y ejecuta SQL read-only, coordina el agente y sirve SSE.
- **`workers/`** — ARQ sobre Redis. Ejecuta jobs asíncronos: import de datasets y el ciclo de vida
  completo del agente (`QUEUED -> ... -> COMPLETED/FAILED/CANCELLED/TIMED_OUT`).
- **`infrastructure/`** — Docker Compose, Prometheus, Grafana, reverse proxy.
- **PostgreSQL** (+ pgvector) como única base de datos de la plataforma.
- **Redis** como broker de la cola ARQ y canal de publicación de eventos de progreso.

```
Usuario -> React (frontend/) -> FastAPI (backend/) -> encola job ARQ
                                     |                        |
                                     |                    workers/
                                     |                        |
                                     |                 Agent Orchestrator
                                     |                        |
                                     |      +-----------------+------------------+
                                     |      |                 |                  |
                                     |  Schema Tool       SQL Tool         Analysis Tool
                                     |      |                 |                  |
                                     |      +-----------------+------------------+
                                     |                        |
                                     |                   PostgreSQL
                                     |                        |
                                     |              eventos de progreso
                                     |                        |
                                     +<----------------- Redis pub/sub
                                     |
                              FastAPI SSE
                                     |
                                React UI
```

## 2. Por qué monolito modular (no microservicios)

El SRS (secciones 5 y 18) exige evitar microservicios prematuros. `backend/` y `workers/`
comparten el mismo código Python (modelos SQLAlchemy, servicios de dominio, SQL validator,
definición de agent tools) importado directamente — no existe un paquete `shared-contracts`
separado. Ver [`adr/0001-monorepo-structure.md`](./adr/0001-monorepo-structure.md).

En la práctica esto se implementa con un **uv workspace** en la raíz del repo: `backend/` y
`workers/` son miembros del mismo workspace, comparten un único `uv.lock` y un único
`.venv`, y `workers` declara `backend` como dependencia editable del workspace. El paquete
instalable de `backend/` se llama `app`; el de `workers/` se llama `tasks` (no `app`,
porque dos paquetes no pueden instalarse con el mismo nombre de módulo top-level en el
mismo entorno) — así, código en `workers/tasks/*` hace `from app.domain... import ...`
directamente.

## 3. Estructura del repositorio

```
ai-data-analyst/
├── backend/     # API, dominio, agente, SQL validator, modelos DB (FastAPI)
├── workers/     # Jobs ARQ: import de datasets, ejecución del agente
├── frontend/    # UI React
├── infrastructure/ # Docker, Prometheus, Grafana, reverse proxy
├── docs/        # Este árbol de documentación
└── .claude/     # Reglas, skills y agentes para trabajar con Claude Code
```

Detalle interno de cada app (routers, servicios, modelos, componentes) se define en Fase 0.1
cuando se agregue el scaffolding real de cada aplicación — no forma parte de esta primera
pasada de estructura/documentación.

## 4. Flujo de una ejecución de análisis

1. Cliente hace `POST /api/v1/analyses` con `dataset_id` y `question`.
2. `backend/` valida RBAC + tenant, crea el registro `analyses` (estado `QUEUED`) y encola un job ARQ.
3. `workers/` toma el job, instancia el agente y transiciona el estado (`PLANNING -> TOOL_RUNNING -> ANALYZING -> GENERATING_RESPONSE`).
4. Cada tool call (`inspect_schema`, `execute_readonly_sql`, `run_analysis`, `create_chart`,
   `search_documents`) se registra en `tool_calls` y publica un evento de progreso en Redis.
5. `backend/` expone `GET /api/v1/analyses/{id}/events` como stream SSE que retransmite esos eventos al cliente.
6. Al finalizar, el resultado queda en `analysis_artifacts`; el estado final es `COMPLETED`,
   `FAILED`, `CANCELLED` o `TIMED_OUT`.

## 5. Aislamiento multi-tenant

Decisión para el MVP (ver [`adr/0003-multi-tenant-isolation.md`](./adr/0003-multi-tenant-isolation.md)):

- Todo modelo con datos de negocio tiene `organization_id`.
- El filtrado por tenant ocurre en la capa de servicio de dominio (`backend/app/domain/*`),
  nunca delegado únicamente al router ni confiado al cliente.
- PostgreSQL Row-Level Security queda como capa de defensa adicional para hardening (Fase 8),
  no como dependencia del MVP.

## 6. Autenticación

Decisión para el MVP (ver [`adr/0002-auth-strategy.md`](./adr/0002-auth-strategy.md)):
credenciales + JWT propio. OIDC queda como extensión posterior, sin bloquear el MVP.

## 7. Gestión de secretos

Decisión para el MVP (ver [`adr/0004-secrets-management.md`](./adr/0004-secrets-management.md)):
cifrado a nivel de aplicación sobre `data_sources.secret_ref` (envelope encryption con clave en
variable de entorno). Un secret manager externo (Vault, AWS Secrets Manager, etc.) queda como
mejora de hardening, no como dependencia del MVP.

## 8. SQL seguro (implementado desde Fase 3a)

- El agente nunca usa la sesión ORM de la plataforma para ejecutar SQL generado — usa un
  engine SQLAlchemy separado (`domain/agent/execution.py`) contra `AGENT_DATABASE_URL`, con
  el rol Postgres **`agent_readonly`** (creado en
  `infrastructure/postgres/init/002-agent-readonly-role.sh`): `SELECT`-only sobre el schema
  `datasets`, sin ningún permiso sobre `public` (donde viven las tablas de la plataforma).
  Esto es una segunda capa de defensa independiente del validador — probado directamente
  (un `UPDATE` o una lectura de `public.users` con SQL sintácticamente válido son rechazados
  por Postgres mismo, no solo por la app).
- Toda consulta del agente pasa por `domain/agent/sql_validator.py` (parser real con
  `sqlglot`, no regex): una sola sentencia `SELECT`, sin `SELECT INTO`, y solo puede
  referenciar la tabla física exacta del dataset autorizado (ni siquiera otro dataset de la
  misma organización — aislamiento de tenant también a nivel SQL, no solo a nivel API).
- Límite de filas (RF-032): el validador inyecta `LIMIT max_rows + 1` en el propio SQL antes
  de ejecutarlo — Postgres nunca calcula más filas de las necesarias, no se trunca después
  de traer todo.
- Timeout (RNF-003): `statement_timeout` fijado a nivel de conexión Postgres, no solo un
  timeout de Python alrededor de la llamada.
- Primer agente (`domain/agent/orchestrator.py`, PydanticAI): tools `inspect_schema` +
  `execute_readonly_sql`, cada tool call queda en `tool_calls` con duración, hash del input
  y resumen del resultado (RF-023, RF-033). Proveedor de LLM: Kimi (Moonshot AI) vía API
  compatible con OpenAI — ver `docs/adr/0009-llm-provider.md`.
- `POST /api/v1/analyses` corre el agente **síncronamente dentro del request** (misma
  decisión que datasets en Fase 2, sección 12) — el estado `QUEUED`/`PLANNING`/
  `TOOL_RUNNING`/etc. se refleja en la respuesta final, no hay streaming SSE todavía.

## 9. Observabilidad

OpenTelemetry instrumenta `backend/` y `workers/`; las métricas se exponen para Prometheus y
se visualizan en Grafana (definiciones versionadas en `infrastructure/`). Cada análisis es
trazable de punta a punta mediante `trace_id` (ver sección 9 del SRS para el detalle de métricas).

## 10. Tooling

- Backend / workers: Python 3.13 gestionado con **uv**.
- Frontend: **pnpm**.
- Justificación en [`adr/0005-tooling.md`](./adr/0005-tooling.md).

## 11. RAG documental (Fase 6)

El SRS menciona `search_documents`, pgvector y "RAG documental" en la arquitectura y el roadmap,
pero no define RF numerados con criterios de aceptación para carga y permisos de documentos.
**Antes de implementar la Fase 6, el SRS debe actualizarse con esos RF específicos.** Este
documento no debe anticipar ni inventar esa especificación funcional.

## 12. Datasets: tablas físicas dinámicas (fuera del ciclo de vida de Alembic)

Cada dataset importado (RF-011) crea una **tabla Postgres real** en el schema `datasets`
(separado de `public`, donde viven las tablas de la plataforma), con columnas inferidas del
CSV/Excel — ver `backend/app/domain/datasets/service.py`. Esto es una excepción deliberada a
la regla general (`.claude/rules/database.md`: "todo cambio de esquema pasa por una migración
Alembic"): el esquema de esas tablas es arbitrario y decidido en runtime por el archivo que
sube cada usuario, no algo que tenga sentido versionar como schema de la plataforma.

Consecuencias a tener presentes:

- `alembic downgrade` de la migración de `datasets`/`data_sources` borra solo el **catálogo**
  (`public.datasets`, `public.data_sources`) — nunca toca el schema `datasets` ni sus tablas
  físicas, porque Alembic no sabe que existen. Un `downgrade base` no deja la base de datos en
  un estado realmente pristino si hay datasets importados.
- Cuando exista borrado de datasets (todavía no implementado), debe borrar la fila de catálogo
  **y** hacer `DROP TABLE datasets.ds_<id>` de forma atómica, en la misma transacción — mismo
  patrón que ya usa `import_file` para crear ambas cosas juntas.
- La creación de la tabla física ocurre en la misma transacción de sesión que el insert del
  catálogo y el `audit_event` (ver `service.py`, `conn = await db.connection()`), así que un
  fallo a mitad de camino no deja tablas huérfanas — pero esto es válido para la ruta de
  *creación*, no para el rollback de Alembic descrito arriba.

**Divergencia conocida con el diagrama de la sección 1**: el diagrama y la sección 4 describen
el import de datasets como un job de `workers/` (ARQ). La implementación actual de Fase 2
ejecuta el import **de forma síncrona dentro del propio request HTTP** (`POST
/api/v1/datasets/import` lee, parsea e inserta todo antes de responder) — es una simplificación
consciente para el MVP de Fase 2, no un error. Si `import_max_rows` (200k por defecto) empieza
a generar timeouts de request reales, mover el import a un job de `workers/` (con polling o
notificación de estado) es el rediseño esperado — no antes, para no construir infraestructura
async sin una necesidad concreta todavía medida.
