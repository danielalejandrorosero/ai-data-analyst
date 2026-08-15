---
name: sync-openapi
description: Exports FastAPI's generated OpenAPI spec into docs/api/ after backend endpoint changes, keeping the versioned API reference in sync with the actual code.
---

# sync-openapi

Exporta el OpenAPI generado automáticamente por FastAPI hacia `docs/api/`.

## Cuándo usarla
Después de agregar, modificar o eliminar un endpoint bajo `/api/v1` (típicamente junto con
`create-endpoint`), para mantener `docs/api/` alineado con el código real en vez de con
lo que el SRS describía originalmente en la sección 7.

## Qué debe garantizar
1. El archivo exportado (`openapi.json`/`openapi.yaml`) en `docs/api/` refleja el schema
   real expuesto por la app, no una copia editada a mano.
2. Se actualiza `docs/api/README.md` si cambia algo relevante para un tercero que quiera
   consumir la API (requisito de portafolio, sección 16 del SRS).
3. No se edita el JSON/YAML exportado a mano — cualquier corrección va en el código fuente
   (docstrings, schemas Pydantic) que genera el OpenAPI.

## Qué NO hace
No sustituye la sección 7 de `docs/SRS.md` (API de referencia a nivel de requisito) — esta
skill mantiene la documentación de implementación, no el requisito funcional.
