---
name: create-page
description: Scaffolds a new route/page in the frontend (route wiring, data fetching via TanStack Query, loading/error/empty states). Use when adding a new top-level screen, not a reusable component.
---

# create-page

Crea una página/ruta nueva siguiendo `frontend/CLAUDE.md` y `.claude/rules/frontend.md`.

## Cuándo usarla
Al agregar una pantalla completa nueva (ej. catálogo de datasets, detalle de análisis,
audit log), no para un componente reutilizable suelto (usa `create-component`).

## Qué debe garantizar
0. Dirección visual vía `frontend-design`/`ui-ux-pro-max` antes de maquetar, e
   `impeccable` (`/impeccable polish` o `/impeccable audit`) sobre el resultado antes de
   darla por terminada — ver "Herramientas de diseño obligatorias" en `frontend/CLAUDE.md`.
1. Ruta registrada en el router del proyecto, con guard de auth/rol si corresponde
   (RF-002, RBAC).
2. Datos remotos vía hook de TanStack Query (`create-query-hook`), nunca fetch directo.
3. Maneja explícitamente los tres estados: cargando, error y vacío — no solo el camino feliz.
4. Si la página muestra progreso de un análisis, usa el hook de consumo SSE existente, no
   reimplementa polling.
5. Layout responsive verificado en desktop y tablet (RNF-030).
6. Esqueleto de test (RTL) para el estado inicial y al menos un estado de error.

## Qué NO hace
No improvisa estilos ad-hoc al margen de las herramientas de diseño del punto 0 ni del
sistema de Tailwind ya establecido (ver `ui-consistency-review`).
