# ADR-0010: Memoria entre análisis del mismo dataset

## Estado
Aceptado — 2026-08-16

## Contexto
El SRS no pide esto explícitamente: RF-020 a RF-025 modelan cada `Analysis` como una
ejecución independiente y autocontenida (`analysis -> agent_run -> tool_calls ->
artifacts`), y RF-050/RF-051 (historial) lo definen como algo que el **usuario** consulta
y reabre, no como contexto que el **agente** reutiliza entre preguntas.

En uso real (probado en vivo contra un dataset real de 95 OTs) esto generó un problema
concreto: cada pregunta nueva sobre el mismo dataset hacía que el agente volviera a
`inspect_schema` y redescubriera todo desde cero, incluso cuando la pregunta anterior ya
había explorado las mismas columnas. Para una sesión de preguntas de seguimiento ("¿qué
tenemos en este backlog?" → "¿cómo lo bajamos?") esto es trabajo repetido y gasta
presupuesto de consultas (`agent_max_queries_per_run`) en volver a aprender lo mismo.

## Decisión
El agente recibe, como contexto de solo lectura antepuesto a la pregunta actual, la
pregunta/respuesta/SQL usado de los últimos `agent_history_max_analyses` (default: 10)
análisis en estado `COMPLETED` del **mismo dataset** — nunca de otros datasets ni de otra
organización (el dataset ya acota por tenant vía FK, no hace falta un filtro adicional de
`organization_id`).

Implementación (`backend/app/domain/agent/orchestrator.py`):
- `_fetch_history`: query simple sobre `Analysis` filtrando por `dataset_id` + `status ==
  COMPLETED` + excluyendo el análisis actual, ordenado por `created_at desc`, acotado por
  el setting.
- `_build_history_context`: arma un bloque de texto con pregunta/respuesta/SQL de cada
  análisis previo.
- El texto se antepone al `question` que se le pasa a `Agent.run(...)` — **no** se
  reconstruye como `message_history` de PydanticAI ni se re-ejecuta ninguna tool call
  previa. El agente puede citar un hallazgo previo, pero si necesita datos frescos tiene
  que volver a consultarlos con las tools (así lo indica el texto del contexto).

## Justificación
- "Todo el historial" en espíritu (no solo el análisis inmediatamente anterior), pero
  acotado en cantidad para no inflar sin límite el tamaño del prompt ni el costo de cada
  corrida — mismo criterio que el resto de los límites del agente
  (`agent_max_queries_per_run`, `agent_max_charts_per_run`).
- Prepender texto al `question` es la opción menos invasiva: no cambia el flujo de tool
  calling, no requiere reconstruir mensajes de PydanticAI con un formato específico del
  proveedor, y queda auditable como texto plano en los logs si hace falta depurarlo.
- No usar `message_history` real evita que el agente "vea" las tool calls previas como si
  fueran parte de la conversación actual — mantiene la frontera de que cada `Analysis`
  sigue siendo la unidad de traza/auditoría (RNF-031), el historial es referencia, no
  continuación de la misma ejecución.

## Consecuencias
- Cada corrida ahora hace una query adicional (barata, con índice por `dataset_id`) antes
  de invocar al agente.
- El campo `Analysis.result_json` (ya usado para RF-042/RF-043) también alimenta el SQL
  citado en el contexto — no se agrega ninguna columna ni tabla nueva.
- El prompt efectivo que ve el modelo crece con el historial - si `agent_history_max_analyses`
  se sube mucho, el costo por corrida sube en proporción. El default (10) es un punto de
  partida, no un valor validado con datos de costo real de producción.
- Si en el futuro se necesita que el agente relance una tool call sobre un hallazgo
  previo (no solo lo cite), esto habría que revisarlo — hoy el contexto es puramente de
  lectura.
