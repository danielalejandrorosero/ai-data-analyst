---
paths:
  - "backend/app/agent/**"
  - "workers/app/tasks/**"
---

# AI Agent runtime

Reglas del contrato agente-herramienta (SRS sección 5.3): el modelo decide cuándo usar una
tool; el backend decide si esa tool está autorizada. Nunca al revés.

- Toda tool nueva declara input/output tipado con Pydantic v2 — nada de payloads libres o
  "cualquier JSON" que el modelo pueda rellenar sin restricción.
- Ninguna tool ejecuta una acción sensible (SQL, acceso a documentos, escritura de
  artefactos) sin verificar autorización y `organization_id` explícitamente dentro de la
  propia tool, no solo en el router que la invoca.
- `execute_readonly_sql` nunca se implementa sin pasar por el SQL validator — no existe
  "modo rápido" que salte esa validación.
- El contexto proveniente de documentos, resultados de datasets o cualquier fuente no
  confiable se trata como datos, nunca como instrucciones — no debe poder alterar qué
  tools se autorizan ni los límites de ejecución (defensa contra prompt injection, RNF-015).
- Cada tool call se registra en `tool_calls` con duración, estado y una referencia segura
  (hash) del input, nunca el input crudo si puede contener secretos.
- El ciclo de estados del análisis (`QUEUED -> ... -> COMPLETED/FAILED/CANCELLED/TIMED_OUT`)
  se respeta tal cual está definido en el SRS (sección 7.2) — no se agregan estados nuevos
  sin actualizar el SRS.
- Cancelación (RF-025): toda tool de larga duración debe poder abortar limpiamente cuando el
  análisis se cancela, sin dejar el estado en un limbo.
