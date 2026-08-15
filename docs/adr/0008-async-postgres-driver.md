# ADR-0008: Driver async de PostgreSQL — asyncpg (no psycopg3)

## Estado
Aceptado — 2026-08-15

## Contexto
El SRS fija SQLAlchemy 2 como ORM, pero no especifica el driver de conexión concreto para
el motor async. Durante el scaffolding inicial se probó `psycopg[binary]` (v3) con
`create_async_engine`, siguiendo lo que se había puesto tentativamente en `.env.example`.

Al probar `/health/ready` corriendo el backend de forma nativa en Windows (sin Docker,
`uv run uvicorn`), la conexión falló con:

```
psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode.
```

Esto es una limitación conocida de psycopg3 async: requiere `SelectorEventLoop`, pero
`ProactorEventLoop` es el event loop por defecto de asyncio en Windows.

## Decisión
Usar **asyncpg** como driver async de PostgreSQL en vez de psycopg3, tanto para el engine
de la aplicación (`app/db/session.py`) como para Alembic (`alembic/env.py`).
`DATABASE_URL` usa el esquema `postgresql+asyncpg://`.

## Justificación
- asyncpg no tiene la restricción de event loop de psycopg3 — funciona igual dentro de
  Docker (Linux) y de forma nativa en Windows, sin configurar un event loop policy
  alternativo.
- Es el driver async más usado con SQLAlchemy 2 + FastAPI en la práctica, con soporte
  maduro para `pgvector` (vía `pgvector-python`).
- No es un cambio "porque sí": surgió de un problema real reproducido al probar
  `/health/ready`, no de preferencia.

## Consecuencias
- No hay conexión sync a Postgres en el proyecto (todo el acceso a la DB de la plataforma
  es async) — si en algún momento se necesita una ruta sync (script puntual, herramienta de
  administración), evaluar agregar `psycopg` solo para ese caso puntual, sin volver a
  usarlo para el engine principal.
- `.env.example` y cualquier ejemplo de `DATABASE_URL` en la documentación usan el esquema
  `postgresql+asyncpg://`.
