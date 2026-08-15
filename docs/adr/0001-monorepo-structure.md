# ADR-0001: Estructura del monorepo (backend/frontend/workers/infrastructure)

## Estado
Aceptado — 2026-08-15

## Contexto
El SRS (Apéndice A, sección 19) propone una estructura `apps/api`, `apps/worker`, `apps/web`,
`packages/shared-contracts`. Esa sección está explícitamente marcada como "estructura
propuesta", no como un requisito funcional numerado (RF/RNF). Se necesitaba una estructura
de trabajo definitiva antes de iniciar Fase 0.

## Decisión
Usar `backend/`, `frontend/`, `workers/`, `infrastructure/` como carpetas de primer nivel,
en lugar de `apps/{api,worker,web}`. No crear un paquete `packages/shared-contracts/`
separado: `backend/` y `workers/` comparten el mismo código Python (modelos, servicios de
dominio, SQL validator, definición de agent tools) importado directamente entre sí, dado que
viven en el mismo monorepo y el mismo lenguaje.

## Justificación
- Nombres más legibles y explícitos para un repositorio de portafolio.
- Evita la complejidad de mantener un paquete compartido separado cuando ambas apps son
  Python y pueden importarse directamente — alineado con el principio del SRS de evitar
  "explosión de complejidad" (sección 18) y microservicios prematuros (sección 5).

## Consecuencias
- `docs/SRS.md` conserva la propuesta original del Apéndice A como referencia histórica,
  señalando que la estructura efectiva es esta.
- Si en el futuro `backend/` y `workers/` necesitan desplegarse desde imágenes con
  dependencias muy distintas, se puede reevaluar extraer un paquete compartido — no antes.
