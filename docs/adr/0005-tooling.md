# ADR-0005: Gestores de dependencias (uv / pnpm)

## Estado
Aceptado — 2026-08-15

## Contexto
El SRS fija el stack tecnológico (Python 3.13, FastAPI, React, TypeScript, etc.) pero no
fija el gestor de dependencias/paquetes, necesario para Dockerfiles, CI y desarrollo local.

## Decisión
- Backend y workers (Python 3.13): **uv**.
- Frontend: **pnpm**.

## Justificación
- `uv` ofrece resolución e instalación rápida y lockfile reproducible, compatible con
  Python 3.13, y simplifica los Dockerfiles de `backend/`/`workers/`.
- `pnpm` reduce duplicación de `node_modules` y tiene lockfile estricto, adecuado para un
  monorepo con una sola app frontend pero con expectativa de builds reproducibles en CI.

## Consecuencias
- CI (GitHub Actions) debe cachear `uv.lock` y `pnpm-lock.yaml`.
- `.claude/settings.json` y las skills relacionadas con backend/frontend asumen estos
  gestores al proponer comandos.
