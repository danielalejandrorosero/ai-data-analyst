# AI Data Analyst

> Plataforma web multi-tenant de análisis de datos asistido por agentes de IA. Proyecto de
> portafolio orientado a Backend Engineering y AI Engineering.

## Estado del proyecto

En Fase 0 (base del repositorio). Todavía no hay funcionalidad de aplicación implementada.
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

Pendiente — `docker-compose.yml` y el scaffolding de cada app se agregan en los siguientes
pasos de Fase 0 / Fase 1. Cuando exista, el flujo será:

```bash
cp .env.example .env
docker compose up -d
```

## Demo / Screenshots

Pendiente — se agregará cuando exista UI funcional.

## Desarrollo local

Pendiente — se documentará junto con el scaffolding de `backend/`, `frontend/` y `workers/`.

## Despliegue

Pendiente — ver sección 11 de [`docs/SRS.md`](docs/SRS.md#11-entorno-y-despliegue) y
[`docs/deployment.md`](docs/deployment.md) (incluye nota sobre Vercel para el frontend).

## Licencia

Pendiente de definir.
