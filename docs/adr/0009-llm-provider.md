# ADR-0009: Proveedor de LLM — Kimi (Moonshot AI)

## Estado
Aceptado — 2026-08-16

## Contexto
El SRS (sección 5.3) exige un runtime de agentes tipado con proveedor de LLM abstraído,
sin fijar cuál usar. Para Fase 3 (SQL Analyst MVP) hace falta un proveedor real con soporte
de tool calling confiable, ya que las tools del agente (`inspect_schema`,
`execute_readonly_sql`) dependen de function calling, no de texto libre.

## Decisión
Usar **Kimi (Moonshot AI)** como proveedor inicial, vía su API compatible con OpenAI
(`LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` configurables en `.env`, sin hardcodear
proveedor en el código — se usa el provider OpenAI-compatible de PydanticAI).

## Justificación
- Costo bajo, relevante para un proyecto de portafolio sin presupuesto de empresa.
- Tool calling compatible con el formato OpenAI, que es lo que PydanticAI espera para
  ejecutar las tools del agente.
- El SRS pide explícitamente "provider abstraído para poder cambiar de proveedor
  posteriormente" — al integrarlo como un provider OpenAI-compatible genérico (no un SDK
  propietario de Moonshot), cambiar a otro proveedor compatible (OpenAI, DeepSeek, etc.)
  más adelante es solo cambiar `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`, no código.

## Consecuencias
- `LLM_BASE_URL` y `LLM_MODEL` quedan sin valor por defecto en `.env.example` — varían
  según la cuenta/plataforma exacta del usuario (China vs. internacional, nombre de modelo
  vigente) y no se hardcodean para evitar apuntar a un endpoint/modelo incorrecto.
- Los tests del agente no dependen de una key real: la lógica de tools, SQL validator y
  orquestación se prueban con el modelo de PydanticAI inyectado/mockeado
  (`TestModel`/`FunctionModel`), no contra la API real de Kimi.
- Si Kimi deja de ser viable (costo, disponibilidad, calidad de tool calling), el cambio de
  proveedor es una edición de configuración, no una reescritura del dominio del agente.
