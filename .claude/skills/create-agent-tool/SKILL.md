---
name: create-agent-tool
description: Scaffolds a new PydanticAI agent tool (typed input/output schema, explicit authorization check, audit hook, negative test) for the agent runtime described in the SRS.
---

# create-agent-tool

Crea o modifica una herramienta del agente (`inspect_schema`, `execute_readonly_sql`,
`run_analysis`, `create_chart`, `search_documents`, o futuras tools aprobadas) siguiendo el
contrato del SRS (sección 5.3): el modelo decide cuándo usar la tool, el backend decide si
está autorizada.

## Cuándo usarla
Al añadir una tool nueva al agente o modificar el contrato (input/output) de una existente.
Es el punto más sensible de seguridad del proyecto (sección 8 del SRS) — no improvisar aquí.

## Qué debe garantizar
1. Input y output tipados con Pydantic v2, sin campos libres que permitan inyectar
   comportamiento no autorizado.
2. Autorización explícita fuera del prompt: la tool verifica permisos/tenant antes de
   ejecutar, no confía en que "el modelo no lo va a pedir".
3. Si la tool toca SQL, pasa obligatoriamente por el SQL validator (nunca bypass directo).
4. Registro en `tool_calls` (agent_run_id, tool, input_hash, duration, status) para
   trazabilidad.
5. Al menos un test negativo que intente un uso no autorizado/destructivo y confirme que
   se bloquea y se audita.

## Qué NO hace
No agrega tools que no estén en la tabla de la sección 5.3 del SRS sin antes discutirlo y,
si corresponde, actualizar el SRS.
