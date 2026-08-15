# Deployment — AI Data Analyst

> Estado: **placeholder de Fase 0**. Documenta la intención, no un pipeline funcional
> todavía. Basado en `docs/SRS.md` sección 11 (Entorno y despliegue) y 11.1 (CI/CD).

## Qué dice el SRS

- Entorno local reproducible vía Docker Compose (`docker compose up -d`) con servicios:
  `frontend`, `api`, `worker`, `postgres`, `redis`, `prometheus`, `grafana`, `reverse-proxy`.
- La infraestructura de producción puede comenzar en una VM o servidor administrado y
  escalarse después, sin rediseñar el dominio.
- Pipeline de CI/CD (GitHub Actions): instalar dependencias + validar lockfiles → lint/format
  → tests unitarios e integración → build frontend/backend → build de imágenes Docker →
  escaneo de dependencias/secretos → publicar artefactos y desplegar a staging → smoke tests.

## Qué falta decidir (no inventar todavía)

El SRS **no fija** el proveedor/target concreto de staging/producción (VM propia, cloud
específico, PaaS). Eso se decide y se documenta como ADR cuando exista una necesidad real
de desplegar — no antes. Ver `.claude/skills/update-adr/SKILL.md`.

**Nota de intención (2026-08-15, no es ADR todavía)**: el usuario planea desplegar el
**frontend** en Vercel más adelante, cuando el proyecto esté más avanzado. Por eso, el
pipeline de CI/CD de GitHub Actions (SRS sección 11.1) queda pospuesto por ahora — Vercel
trae su propio build/deploy automático por push, así que un GitHub Actions completo podría
terminar siendo redundante para el frontend. Esto **no** decide todavía qué pasa con
backend/worker/postgres/redis/observabilidad (el SRS asume Docker Compose sobre una VM o
servidor administrado para eso, sección 11) — Vercel no aloja ese tipo de stack. Cuando se
retome este tema, formalizar como ADR (con `update-adr`) cubriendo: qué se despliega en
Vercel, qué sigue en Docker Compose/VM, y cómo se conectan (CORS, URLs de API, variables de
entorno del frontend).

## Scripts placeholder

- `infrastructure/scripts/deploy-staging.sh`
- `infrastructure/scripts/deploy-production.sh`
- `infrastructure/scripts/smoke-test.sh`

Ninguno ejecuta un despliegue real todavía — fallan explícitamente con un mensaje claro.
Se implementan cuando exista: `docker-compose.yml`, imágenes Docker construibles, y un
target de staging aprobado.

## Orden esperado de implementación

1. `docker-compose.yml` local funcional (Fase 0.2).
2. CI en GitHub Actions ejecutando lint + tests (a partir de Fase 0.2/1).
3. Build de imágenes Docker reproducible.
4. Decisión de target de staging (ADR) + implementación real de `deploy-staging.sh`.
5. `deploy-production.sh` recién después de Fase 8 (hardening, SRS sección 13).
