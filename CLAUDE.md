# AI Data Analyst — CLAUDE.md

## Qué es
Plataforma web multi-tenant para preguntar datos en lenguaje natural. Un agente de IA
tipado inspecciona esquemas, genera SQL de solo lectura, ejecuta análisis (Polars) y
genera visualizaciones, con trazabilidad completa
(`analysis -> agent_run -> tool_calls -> artifacts`).

Proyecto de portafolio orientado a Backend Engineering + AI Engineering.

## Documentación — quién manda qué
Este repositorio separa deliberadamente tres capas de documentación. No mezclar su contenido:

- **`docs/SRS.md`** — el **QUÉ**. Requisitos funcionales y no funcionales, alcance, criterios
  de aceptación. Es la fuente de verdad funcional (SRS-ADA-001 v1.0). Cambiarlo requiere
  actualizar el ID del requisito afectado.
- **`docs/architecture.md`** — el **CÓMO**. Cómo se construye lo que el SRS pide: estructura
  del monorepo, flujo de ejecución, componentes.
- **`docs/adr/`** — el **POR QUÉ**. Decisiones técnicas concretas (auth, secretos, tenancy,
  tooling) con su justificación y consecuencias.

Al implementar algo, si el SRS no lo pide, no se construye (sin discutirlo antes). Si hace
falta una decisión técnica que el SRS no fija, se propone, se discute y se documenta como
ADR — no se decide en silencio ni se escribe dentro del SRS.

## Objetivo principal
Responder preguntas de negocio sobre datos sin requerir SQL del usuario, con seguridad
controlada por software (no por el LLM) y trazabilidad end-to-end.

## Stack
- Backend: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic — gestionado con **uv**
- Frontend: React, TypeScript, Vite, Tailwind, TanStack Query, Recharts (+ Zustand si aplica) — gestionado con **pnpm**
- Data: PostgreSQL + pgvector, Polars
- Infra: Redis, ARQ, Docker Compose
- AI: PydanticAI, LLM provider abstraído (sin proveedor fijo)
- Testing: Pytest, Vitest, React Testing Library, Playwright
- Observability: OpenTelemetry, Prometheus, Grafana
- CI/CD: GitHub Actions

## Arquitectura (resumen)
Monolito modular en Python. FastAPI (`backend/`) expone `/api/v1`, gestiona
auth/RBAC/tenant scoping y encola análisis. Workers ARQ (`workers/`) ejecutan el agente
(tools: inspect_schema, execute_readonly_sql, run_analysis, create_chart, search_documents)
y publican progreso vía Redis. FastAPI transmite ese progreso por SSE. React (`frontend/`)
consume la API y el stream. Detalle completo: `docs/architecture.md`.

## Estructura del repositorio
- `backend/` — API, dominio, agente, SQL validator, modelos DB
- `workers/` — jobs ARQ (import de datasets, ejecución del agente)
- `frontend/` — UI React
- `infrastructure/` — Docker, Prometheus, Grafana, reverse proxy
- `docs/` — SRS, arquitectura, ADRs, threat model, API
- `.claude/` — reglas, skills y agentes de Claude Code

## Comandos principales
(se completa cuando exista scaffolding real de cada app — pendiente más allá de Fase 0)

## Convenciones importantes
- API versionada explícita: `/api/v1/...`
- Todo dato de negocio se filtra por `organization_id` en la capa de servicio de dominio
- El ORM de la plataforma (SQLAlchemy) y el SQL generado por el agente nunca comparten
  ruta de ejecución ni credenciales
- El modelo decide qué tool usar; el backend decide si esa tool está autorizada — nunca al revés

## Reglas críticas (no negociables)
- Las consultas del agente son SIEMPRE read-only, sobre credenciales de solo lectura.
  Nunca INSERT/UPDATE/DELETE/DDL por el canal del agente.
- Ningún secreto en texto plano en tablas de negocio, logs o el repositorio.
- RBAC + aislamiento por tenant en toda operación protegida.
- Todo tool call del agente queda auditado y trazado (trace_id).

## Cierre de fases
Ninguna fase del roadmap (SRS sección 13) se da por terminada sin antes correr la skill
`phase-dod-check`, que empieza armando una tabla explícita de cada RF/RNF/CU de esa fase
(hecho / diferido y ya acordado / faltante) — no alcanza con que los tests pasen. Si algo
queda afuera sin haberlo comunicado antes, se avisa ahí mismo, no se calla.

## Restricciones de seguridad
Ver `.claude/rules/security.md` y `docs/security/threat-model.md`. Nunca desactivar SQL
validation, rate limits o RBAC "para probar más rápido".

## Referencia
Fuente de verdad funcional: `docs/SRS.md`. Todo cambio de comportamiento funcional,
seguridad, datos, contratos API o arquitectura debe reflejarse ahí antes de darse por
terminado.
