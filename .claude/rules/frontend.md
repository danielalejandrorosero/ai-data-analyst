---
paths:
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
---

# Frontend conventions

Convenciones de código para `frontend/` (React + TypeScript + Vite), gestionado con
**pnpm**. Complementa `frontend/CLAUDE.md`, no lo repite.

- Toda llamada a la API pasa por un hook de TanStack Query dedicado en `src/api/` — no
  hacer `fetch`/`axios` sueltos dentro de componentes.
- Zustand solo se introduce cuando exista un estado local/global concreto que TanStack
  Query no pueda modelar (no "por si acaso").
- El consumo del stream SSE de un análisis vive en un hook dedicado y reutilizable, no
  duplicado por feature.
- Componentes de features (`src/features/*`) no importan directamente entre sí — comparten
  vía `src/lib/` o `src/components/` si es UI genérica.
- Tipos generados o alineados con los schemas Pydantic del backend (manual o vía OpenAPI)
  para mantener el contrato consistente entre frontend y backend.
