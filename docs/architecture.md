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

## 8. SQL seguro

- El agente nunca usa la sesión ORM de la plataforma para ejecutar SQL generado.
- Toda consulta del agente pasa por un validador (allowlist de `SELECT` + expresiones
  autorizadas) antes de llegar a la fuente externa.
- Las conexiones externas usadas por el agente son siempre de solo lectura.
- Timeout y límite de filas configurables (ver `RF-032`, `RNF-003` en el SRS).

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
