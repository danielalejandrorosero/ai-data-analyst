# AI Data Analyst

> Plataforma web multi-tenant de análisis de datos asistido por agentes de IA. Proyecto de
> portafolio orientado a Backend Engineering y AI Engineering.

## Estado del proyecto

Fase 0 (base del repositorio) + Fase 1 (auth + tenants) + Fase 2 (datasets) + Fase 3
(SQL Analyst MVP + conexiones PostgreSQL externas) + Fase 4 (agent runtime: multi-paso,
cancelación, progreso en vivo) + Fase 5 (análisis con Polars, gráficos, export) completas.

- Auth real por credenciales + JWT (registro, login, roles OWNER/ADMIN/ANALYST/VIEWER,
  aislamiento por `organization_id`, audit log de éxitos y fallos): `POST /api/auth/register`,
  `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/organizations`,
  `GET /api/audit-events`.
- Import de datasets CSV/Excel real (no un mock): `POST /api/datasets/import` parsea el
  archivo, valida tamaño/filas, y carga los datos en una tabla física de PostgreSQL (schema
  `datasets`) — no queda como archivo suelto. `GET /api/datasets`,
  `GET /api/datasets/{id}/schema` para el catálogo.
- Agente + SQL seguro real, ahora asíncrono (RF-020 a RF-025): `POST /api/analyses`
  encola el análisis como job de `workers/` (ARQ) y responde `202` de inmediato en
  `QUEUED` — el agente (PydanticAI + Kimi) inspecciona el esquema y puede ejecutar más de
  una consulta de solo lectura por pregunta compleja (hasta un límite configurable),
  validada por un parser real (`sqlglot`) y por un rol Postgres separado sin permisos de
  escritura ni acceso a las tablas de la plataforma. `GET /api/analyses/{id}` para
  consultar el resultado y el trace de tool calls, `GET /api/analyses` para el historial,
  `GET /api/analyses/{id}/events` para progreso en vivo por SSE, y
  `POST /api/analyses/{id}/cancel` para abortar una ejecución en curso.
- Conexiones externas PostgreSQL (RF-010): `POST /api/datasets/connections` (rol
  OWNER/ADMIN) prueba la conexión con un `SELECT 1` controlado antes de guardar nada, y
  cifra la credencial (Fernet). MySQL queda diferido explícitamente (ver
  `docs/architecture.md` sección 8.1) — el agente todavía no ejecuta consultas contra estas
  conexiones, solo quedan registradas.
- Análisis con Polars y gráficos (RF-040 a RF-043): el agente puede post-procesar
  (agrupar/agregar/ordenar) el resultado de una consulta con `run_analysis`, y generar
  especificaciones de gráfico (no imágenes) con `create_chart`, consumibles por un frontend
  con Recharts. `GET /api/analyses/{id}/artifacts` para los gráficos generados,
  `GET /api/analyses/{id}/export?format=csv|json` para descargar un resultado.

RAG documental es Fase 6 en adelante. El frontend (React + Vite + TypeScript + Tailwind
CSS v4 + TanStack Query) tiene por ahora las pantallas de login y registro, consumiendo
el backend real (`frontend/`, ver `frontend/README.md`) — el resto de las pantallas
(datasets, análisis, gráficos) se construyen fase por fase, siguiendo el mismo roadmap
que el backend.

**Importante**: desde Fase 4, `POST /api/analyses` responde `202` con `QUEUED` de
inmediato — el `worker` (ARQ) tiene que estar corriendo para que el análisis avance en
absoluto, si no se queda en `QUEUED` para siempre. `docker compose up -d` ya lo incluye,
pero si corrés el backend nativo sin Docker acordate de levantarlo aparte (ver más abajo).
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
| [`docs/api/`](docs/api/) | Referencia de la API `/api` |

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

Con Docker (recomendado; validado end-to-end — `api`/`postgres`/`redis`/`worker` arriba y
`/health/ready` en 200). El servicio `frontend` (dev server de Vite) también está declarado
en `docker-compose.yml`, corriendo en `http://localhost:5173` — todavía no se validó
levantándolo con Docker en esta máquina, así que si algo falla ahí avisá:

```bash
cp .env.example .env
docker compose up -d
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_data_analyst" \
  uv run --package backend alembic -c backend/alembic.ini upgrade head
```

El `docker compose up -d` no corre migraciones solo — un volumen recién creado queda con
`/health/ready` en `200` (solo chequea conectividad) pero **sin ninguna tabla**, así que el
paso de `alembic upgrade head` de arriba es obligatorio la primera vez (o después de borrar
el volumen de Postgres). El rol `agent_readonly` sí se crea automáticamente en un volumen
nuevo, vía `infrastructure/postgres/init/`.

pgAdmin queda disponible en `http://localhost:5050` (login: `PGADMIN_DEFAULT_EMAIL`/
`PGADMIN_DEFAULT_PASSWORD` de tu `.env`, por defecto `admin@local.dev` / ver
`.env.example`) — es solo una herramienta de desarrollo local, no forma parte del roadmap.
Para conectarlo a la DB del proyecto: nuevo servidor, host `postgres` (nombre del servicio
en la red de Docker, no `localhost`), puerto `5432`, usuario/password de `POSTGRES_USER`/
`POSTGRES_PASSWORD`.

Todo funciona sin `LLM_API_KEY` **excepto** procesar el análisis en sí: `POST /api/analyses`
igual responde `202`/`QUEUED` (eso no depende del LLM), pero el `worker` lo deja en
`FAILED` con un mensaje claro apenas lo levanta (ver `GET /api/analyses/{id}` o los logs
de `worker` — no rompe el resto de la app). Para que el agente funcione de verdad, completá
en `.env`: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL` y `LLM_MODEL` con los datos de tu
cuenta de Kimi (Moonshot AI) — ver [`docs/adr/0009-llm-provider.md`](docs/adr/0009-llm-provider.md).

Sin Docker, corriendo el backend nativo (requiere `uv`, y Postgres/Redis disponibles por
tu cuenta o vía `docker compose up postgres redis`) — necesitás **dos** procesos, la API
y el worker, o los análisis nunca avanzan de `QUEUED`:

```bash
cp .env.example .env
uv sync
uv run --package backend uvicorn app.main:app --reload
# en otra terminal:
uv run --package workers arq tasks.worker_settings.WorkerSettings
```

Verificación rápida: `curl http://localhost:8000/health/live` debe responder
`{"status":"ok"}`.

## Demo / Screenshots

Pendiente agregar capturas — ya existe UI funcional (login/registro en
`http://localhost:5173`), pero todavía no se subieron imágenes al repo.

## Desarrollo local

`backend/` y `workers/` son miembros de un **uv workspace** (un solo `uv.lock`/`.venv` en
la raíz). Comandos útiles desde la raíz del repo:

```bash
uv sync                                              # instala todo el workspace
uv run --package backend pytest backend/tests         # tests de backend
uv run --package backend ruff check backend/app       # lint
uv run --package backend alembic revision --autogenerate -m "mensaje"
uv run --package backend alembic upgrade head
```

Los tests de integración de `backend/` corren contra una base de datos de test real
(`ai_data_analyst_test`, no mocks), no la de desarrollo. Si no existe todavía:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE ai_data_analyst_test;"
docker compose exec postgres psql -U postgres -d ai_data_analyst_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

El rol `agent_readonly` (usado por el agente para SQL de solo lectura, ver
`docs/architecture.md` sección 8) solo se crea automáticamente en la base de datos de
desarrollo (vía `infrastructure/postgres/init/`, que corre una sola vez al crear el
volumen). Para la base de test, crearlo a mano una vez:

```bash
docker compose exec postgres psql -U postgres -d ai_data_analyst_test -c "
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'agent_readonly') THEN
    CREATE ROLE agent_readonly WITH LOGIN PASSWORD 'changeme_agent_readonly';
  END IF;
END \$\$;"
```

(El `conftest.py` de los tests ya se encarga de crear el schema `datasets` y otorgarle los
permisos correspondientes en cada corrida — este paso solo crea el rol una vez.)

`frontend/` es un proyecto pnpm independiente (no forma parte del uv workspace del
backend). Comandos desde `frontend/`:

```bash
cp .env.example .env.local
pnpm install
pnpm dev            # http://localhost:5173, requiere la API corriendo
pnpm test           # Vitest + Testing Library
pnpm lint           # oxlint
pnpm build          # type-check (tsc) + build de producción
```

## Despliegue

Pendiente — ver sección 11 de [`docs/SRS.md`](docs/SRS.md#11-entorno-y-despliegue) y
[`docs/deployment.md`](docs/deployment.md) (incluye nota sobre Vercel para el frontend).

## Licencia

Pendiente de definir.
