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
1. Ruta registrada en el router del proyecto, con guard de auth/rol si corresponde
   (RF-002, RBAC).
2. Datos remotos vía hook de TanStack Query (`create-query-hook`), nunca fetch directo.
3. Maneja explícitamente los tres estados: cargando, error y vacío — no solo el camino feliz.
4. Si la página muestra progreso de un análisis, usa el hook de consumo SSE existente, no
   reimplementa polling.
5. Layout responsive verificado en desktop y tablet (RNF-030).
6. Esqueleto de test (RTL) para el estado inicial y al menos un estado de error.

## Qué NO hace
No decide el diseño visual desde cero — reutiliza el sistema de Tailwind ya establecido
(ver `ui-consistency-review`) en vez de introducir estilos ad-hoc.
