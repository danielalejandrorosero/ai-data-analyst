# workers/ — CLAUDE.md

ARQ sobre Redis, gestionado con **uv**. Ejecuta imports de datasets y el ciclo del agente
(`QUEUED -> PLANNING -> TOOL_RUNNING -> ANALYZING -> GENERATING_RESPONSE ->
COMPLETED/FAILED/CANCELLED/TIMED_OUT`).

El paquete instalable de esta app se llama `tasks/` (no `app/`): `backend/` y `workers/`
comparten un mismo venv de workspace (uv workspace), y dos paquetes no pueden instalarse
ambos como un módulo top-level llamado `app` en el mismo entorno. `workers` depende de
`backend` como miembro del workspace, así que el código de `workers/tasks/*` importa
directamente `from app.domain...`, `from app.core...`, etc.

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
