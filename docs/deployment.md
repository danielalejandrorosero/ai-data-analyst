# Deployment — AI Data Analyst

> Estado (2026-08-16, Fase 8): entorno local + CI reales y funcionando. **Despliegue a
> staging/producción sigue sin decidirse** — esa parte de este documento sigue siendo
> intención, no implementación. Basado en `docs/SRS.md` sección 11 (Entorno y despliegue)
> y 11.1 (CI/CD).

## Qué ya funciona

- **Entorno local reproducible** vía Docker Compose (`docker compose up -d`):
  `frontend`, `api`, `worker`, `postgres` (con `pgvector`), `redis`, `pgadmin` (tooling de
  desarrollo). `prometheus`/`grafana`/`reverse-proxy` quedan para Fase 7 (Observabilidad,
  diferida a propósito — ver `docs/SRS.md` sección 13, sin necesidad concreta de tráfico
  real todavía que justifique el costo de montarlos).
- **CI en GitHub Actions** (`.github/workflows/ci.yml`, agregado en Fase 8): lint + tests
  de integración del backend (con Postgres/Redis reales como `services:` del job, no
  mocks — mismo criterio de `.claude/rules/testing.md`) + lint/tests/build del frontend +
  build de las 3 imágenes Docker, en cada push/PR a `main`/`develop`. Cubre la primera
  mitad del pipeline que pedía SRS 11.1 (instalar deps → lint → tests → build); todavía
  **no** hace escaneo de dependencias/secretos, ni publica artefactos, ni despliega a
  staging — no hay staging todavía (ver abajo).

## Qué falta decidir (no inventar todavía)

El SRS **no fija** el proveedor/target concreto de staging/producción (VM propia, cloud
específico, PaaS). Eso se decide y se documenta como ADR cuando exista una necesidad real
de desplegar — no antes. Ver `.claude/skills/update-adr/SKILL.md`.

**Nota de intención (2026-08-15, sigue sin ser ADR)**: el usuario planea desplegar el
**frontend** en Vercel más adelante. Vercel trae su propio build/deploy automático por
push, así que **no** haría falta que el CI de GitHub Actions también despliegue el
frontend — solo lo valida (lint/test/build) antes de que Vercel lo tome. Esto **no**
decide todavía qué pasa con backend/worker/postgres/redis (el SRS asume Docker Compose
sobre una VM o servidor administrado para eso, sección 11) — Vercel no aloja ese tipo de
stack. Cuando se retome este tema, formalizar como ADR (con `update-adr`) cubriendo: qué
se despliega en Vercel, qué sigue en Docker Compose/VM, y cómo se conectan (CORS, URLs de
API, variables de entorno del frontend).

## Scripts placeholder

- `infrastructure/scripts/deploy-staging.sh`
- `infrastructure/scripts/deploy-production.sh`
- `infrastructure/scripts/smoke-test.sh`

Ninguno ejecuta un despliegue real todavía — fallan explícitamente con un mensaje claro.
Se implementan cuando exista un target de staging aprobado (ya existen `docker-compose.yml`
e imágenes Docker construibles, eso ya no es lo que falta).

## Orden esperado de implementación

1. ~~`docker-compose.yml` local funcional~~ — hecho.
2. ~~CI en GitHub Actions ejecutando lint + tests~~ — hecho (Fase 8).
3. ~~Build de imágenes Docker reproducible~~ — hecho, parte del CI.
4. Decisión de target de staging (ADR) + implementación real de `deploy-staging.sh`.
5. `deploy-production.sh` recién después de cerrar Fase 8 (SRS sección 13).
