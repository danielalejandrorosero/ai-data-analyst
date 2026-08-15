# frontend/ — CLAUDE.md

React + TypeScript + Vite. Gestionado con **pnpm**. TanStack Query es la fuente de verdad
para datos remotos; Zustand solo si un estado local/global realmente lo requiere.

## Reglas específicas
- No duplicar en Zustand estado que ya vive en TanStack Query.
- El progreso de un análisis se consume vía SSE (`/api/v1/analyses/{id}/events`); no hacer
  polling salvo fallback explícito.
- La UI distingue visualmente: respuesta final, tool ejecutada, SQL generado y errores —
  nunca en el mismo bloque visual (RNF-031).
- Gráficos con Recharts sobre datos ya validados por el backend; el frontend no ejecuta SQL
  ni transforma datos "a ciegas".
- Componentes responsive/accesibles en desktop y tablet (RNF-030).

Ver también `.claude/rules/frontend.md`, `.claude/rules/testing.md`.
