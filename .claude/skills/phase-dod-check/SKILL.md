---
name: phase-dod-check
description: Verifies the Definition of Done (SRS section 13.1) against the current roadmap phase before it's marked complete. Use before closing out a Fase (0-8) from docs/SRS.md.
---

# phase-dod-check

Verifica la Definición de Terminado (DoD, sección 13.1 del SRS) para la fase del roadmap
que se está cerrando.

## Cuándo usarla
Antes de dar por cerrada cualquier fase del roadmap (`docs/SRS.md`, sección 13).

## Checklist (DoD del SRS, tal cual)
1. Código formateado y lint sin errores críticos.
2. Pruebas automatizadas pasando.
3. Cada requisito de la fase está implementado y asociado a al menos un test.
4. Logs y métricas disponibles para lo implementado en esta fase.
5. No existen secretos en el repositorio (correr el mismo tipo de escaneo usado en Fase 0).
6. Docker Compose levanta el entorno desde cero incluyendo lo nuevo de esta fase.
7. README actualizado si la fase agrega instalación/arquitectura/troubleshooting relevante.
8. Criterios de aceptación de la fase verificados manual o automáticamente.

## Qué NO hace
No decide por su cuenta que una fase está completa — reporta el estado de cada ítem del
checklist para que el usuario confirme el cierre.
