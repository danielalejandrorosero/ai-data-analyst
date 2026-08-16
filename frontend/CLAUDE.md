# frontend/ — CLAUDE.md

React + TypeScript + Vite. Gestionado con **pnpm**. TanStack Query es la fuente de verdad
para datos remotos; Zustand solo si un estado local/global realmente lo requiere.

## Herramientas de diseño obligatorias

Para **cualquier** trabajo de UI en `frontend/` (crear, rediseñar, ajustar estilos, revisar
una pantalla o componente) se usan siempre estos 3 plugins instalados (alcance usuario,
`claude plugin list` los muestra activos) — nunca se diseña "a mano" sin pasar por ellos
primero:

1. **`frontend-design`** (oficial de Anthropic) — dirección estética, tipografía, evitar el
   look genérico de IA. Punto de partida para cualquier pantalla o componente nuevo.
2. **`ui-ux-pro-max`** — bases de datos de estilos/paletas/tipografía/UX guidelines
   específicas del stack (React + Tailwind + shadcn/ui en este proyecto).
3. **`impeccable`** — pulido, auditoría de anti-patrones y crítica de UI ya construida
   (`/impeccable polish`, `/impeccable audit`, `/impeccable critique`).

Flujo esperado: `frontend-design`/`ui-ux-pro-max` para la dirección inicial de una pantalla
o componente nuevo, `impeccable` para revisar/pulir lo ya construido antes de darlo por
terminado — no es opcional, no se salta "para ir más rápido".

## Reglas específicas
- No duplicar en Zustand estado que ya vive en TanStack Query.
- El progreso de un análisis se consume vía SSE (`/api/analyses/{id}/events`); no hacer
  polling salvo fallback explícito.
- La UI distingue visualmente: respuesta final, tool ejecutada, SQL generado y errores —
  nunca en el mismo bloque visual (RNF-031).
- Gráficos con Recharts sobre datos ya validados por el backend; el frontend no ejecuta SQL
  ni transforma datos "a ciegas".
- Componentes responsive/accesibles en desktop y tablet (RNF-030).

Ver también `.claude/rules/frontend.md`, `.claude/rules/testing.md`.
