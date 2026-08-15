#!/usr/bin/env bash
# Placeholder — Fase 0. No ejecuta ningún despliegue real todavía.
#
# Plan (SRS docs/SRS.md, sección 11 y 11.1, y docs/deployment.md):
#   1. Build de imágenes Docker de backend/frontend/workers.
#   2. Push a registry.
#   3. Deploy a la VM/servidor de staging (target concreto aún no decidido, ver
#      docs/deployment.md).
#   4. Ejecutar migraciones Alembic contra la DB de staging.
#   5. Ejecutar smoke tests (ver infrastructure/scripts/smoke-test.sh).
#
# No implementar contra un entorno real hasta que exista docker-compose.yml,
# imágenes construibles y un target de staging decidido y aprobado.

set -euo pipefail

echo "deploy-staging: pendiente de implementación (Fase 0.2+)."
echo "Ver docs/deployment.md para el plan y docs/adr/ para decisiones relacionadas."
exit 1
