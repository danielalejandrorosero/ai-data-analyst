# API — AI Data Analyst

Este directorio contendrá la documentación de la API versionada `/api/v1`.

## Estado actual (Fase 0)

Todavía no existe implementación de backend, por lo tanto no hay OpenAPI generado. La
API de referencia (rutas, propósito) está definida en la sección 7 del
[SRS](../SRS.md#7-api-de-referencia).

## Plan para fases posteriores

- A partir de Fase 1, FastAPI expondrá `/api/v1/openapi.json` automáticamente.
- Este directorio guardará un snapshot exportado del OpenAPI (`openapi.json` /
  `openapi.yaml`) como referencia versionada, actualizado en cada release relevante.
- Ejemplos de requests/responses reales (incluyendo ejemplos de preguntas y respuestas del
  agente, requeridos por la sección 16 del SRS) se agregarán aquí a medida que existan
  endpoints funcionales.
