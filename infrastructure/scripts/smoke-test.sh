#!/usr/bin/env bash
# Placeholder — Fase 0. Smoke tests post-deploy (SRS docs/SRS.md, sección 11.1).
#
# Plan cuando exista la app real:
#   - GET /health/live  -> 200
#   - GET /health/ready -> 200 (con dependencias críticas realmente arriba)
#   - Login de un usuario de prueba -> sesión válida
#   - Un análisis mínimo de extremo a extremo (criterio de aceptación, SRS sección 15)

set -euo pipefail

echo "smoke-test: pendiente de implementación (requiere backend real con /health/*)."
exit 1
