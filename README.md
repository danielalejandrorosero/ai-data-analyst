# AI Data Analyst

> Plataforma web multi-tenant de análisis de datos asistido por agentes de IA. Proyecto de
> portafolio orientado a Backend Engineering y AI Engineering.

## Estado del proyecto

Fase 0 (base del repositorio) + scaffolding inicial de backend/workers. Existe un FastAPI
mínimo con health checks reales (`/health/live`, `/health/ready`) y un worker ARQ vacío,
pero **todavía no hay funcionalidad de negocio** (auth, datasets, agente, etc. — eso es
Fase 1 en adelante). El frontend todavía no tiene scaffolding.
Ver el roadmap completo en [`docs/SRS.md`](docs/SRS.md#13-roadmap-de-implementación).

## Problema

Permitir que un usuario haga preguntas de negocio sobre sus datos en lenguaje natural, sin
requerir conocimiento de SQL, mientras un agente de IA inspecciona esquemas, genera y valida
consultas SQL de solo lectura, y produce respuestas con evidencia trazable.

## Documentación

Este repositorio separa deliberadamente tres capas de documentación:

| Documento | Responde a |
|---|---|
| [`docs/SRS.md`](docs/SRS.md) | **Qué** debe hacer el sistema (requisitos, alcance, criterios de aceptación) |
| [`docs/architecture.md`](docs/architecture.md) | **Cómo** se construye (estructura, flujo, componentes) |
| [`docs/adr/`](docs/adr/) | **Por qué** se tomó cada decisión técnica relevante |
| [`docs/security/threat-model.md`](docs/security/threat-model.md) | Amenazas y controles de seguridad |
| [`docs/api/`](docs/api/) | Referencia de la API `/api/v1` |

## Stack

- **Backend**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic (gestionado con `uv`)
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts (gestionado con `pnpm`)
- **Data**: PostgreSQL + pgvector, Polars
- **Infra**: Redis, ARQ, Docker Compose
- **AI**: PydanticAI, proveedor de LLM abstraído
- **Testing**: Pytest, Vitest, React Testing Library, Playwright
- **Observabilidad**: OpenTelemetry, Prometheus, Grafana
- **CI/CD**: GitHub Actions

## Arquitectura

Monolito modular en Python (evita microservicios prematuros). Ver diagrama y detalle en
[`docs/architecture.md`](docs/architecture.md).

## Repositorio

```bash
git clone https://github.com/danielalejandrorosero/ai-data-analyst.git
cd ai-data-analyst
git checkout develop
```

Ramas: `main` (estable) y `develop` (integración). Ver
[`docs/adr/0006-branching-strategy.md`](docs/adr/0006-branching-strategy.md).

## Instalación local

Con Docker (recomendado, aún no probado end-to-end en esta máquina por falta de Docker
local — si te falla algo avisá):

```bash
cp .env.example .env
docker compose up -d
```

Sin Docker, corriendo el backend nativo (requiere `uv`, y Postgres/Redis disponibles por
tu cuenta o vía `docker compose up postgres redis`):

```bash
cp .env.example .env
uv sync
uv run --package backend uvicorn app.main:app --reload
```

Verificación rápida: `curl http://localhost:8000/health/live` debe responder
`{"status":"ok"}`.

## Demo / Screenshots

Pendiente — se agregará cuando exista UI funcional.

## Desarrollo local

`backend/` y `workers/` son miembros de un **uv workspace** (un solo `uv.lock`/`.venv` en
la raíz). Comandos útiles desde la raíz del repo:

```bash
uv sync                                              # instala todo el workspace
uv run --package backend pytest                      # tests de backend
uv run --package backend ruff check backend/app       # lint
uv run --package backend alembic revision --autogenerate -m "mensaje"
uv run --package backend alembic upgrade head
```

`frontend/` todavía no tiene scaffolding — pendiente.

## Despliegue

Pendiente — ver sección 11 de [`docs/SRS.md`](docs/SRS.md#11-entorno-y-despliegue) y
[`docs/deployment.md`](docs/deployment.md) (incluye nota sobre Vercel para el frontend).

## Licencia

Pendiente de definir.
