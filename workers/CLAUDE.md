# workers/ — CLAUDE.md

ARQ sobre Redis, gestionado con **uv**. Ejecuta imports de datasets y el ciclo del agente
(`QUEUED -> PLANNING -> TOOL_RUNNING -> ANALYZING -> GENERATING_RESPONSE ->
COMPLETED/FAILED/CANCELLED/TIMED_OUT`).

## Reglas específicas
- Cada job respeta el timeout configurable (default 30s, RNF-003) y debe abandonar el
  procesamiento si el análisis fue cancelado (RF-025).
- Los jobs publican eventos de progreso a Redis; la API los transmite por SSE — no acoplar
  el worker al ciclo de vida HTTP.
- Toda excepción de un tool call se registra en `tool_calls` y transiciona el análisis a
  FAILED — nunca dejarlo en un estado intermedio.
- Reutiliza los mismos servicios de dominio de `backend/` para autorización — no
  reimplementar reglas de permisos aquí.

Ver también `.claude/rules/ai-agent.md`, `.claude/rules/security.md`.
