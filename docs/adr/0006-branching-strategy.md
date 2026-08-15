# ADR-0006: Estrategia de ramas

## Estado
Aceptado — 2026-08-15

## Contexto
El SRS no define estrategia de control de versiones (no es un requisito funcional). Se
necesita una convención simple para trabajar por fases (`docs/SRS.md`, sección 13) sin
fricción, dado que el proyecto es de un solo desarrollador con apoyo de Claude Code.

## Decisión
- `main`: rama estable. Solo recibe merges desde `develop` cuando una fase (o un conjunto
  de commits coherente) pasa su Definition of Done (SRS sección 13.1, skill
  `phase-dod-check`).
- `develop`: rama de integración. Todo el trabajo en curso se integra aquí primero.
- Ramas de trabajo de corta duración, con prefijo por tipo, creadas desde `develop`:
  - `feature/<fase>-<descripcion>` (ej. `feature/fase1-auth-login`)
  - `fix/<descripcion>`
  - `chore/<descripcion>` (tooling, docs, configuración de Claude Code)

## Justificación
- Un modelo `main`/`develop` simple es suficiente para un proyecto de portafolio de un
  desarrollador — un Gitflow completo (release branches, hotfix branches formales) sería
  complejidad prematura, igual que se decidió para la arquitectura (ADR-0001).
- Prefijar por fase en `feature/` mantiene trazabilidad directa con el roadmap del SRS.

## Consecuencias
- CI (cuando exista) corre en PRs hacia `develop` y `main`.
- `main` debe poder desplegarse en cualquier momento sin trabajo a medio terminar.
- Si el proyecto crece a más de un colaborador, esta estrategia se revisita con un nuevo ADR.
