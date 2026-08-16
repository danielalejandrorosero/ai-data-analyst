---
paths:
  - "backend/app/db/**"
  - "backend/alembic/**"
---

# Database

Convenciones de persistencia (SRS sección 6 y 6.1, `docs/adr/0003-multi-tenant-isolation.md`,
`docs/adr/0004-secrets-management.md`).

- Toda tabla con datos de negocio incluye `organization_id`, y todo query de dominio lo
  filtra explícitamente — el aislamiento de tenant no es opcional ni "se agrega después".
  Excepción aceptada y consciente: tablas que cuelgan directo de `analyses` con FK
  `ON DELETE CASCADE` (`agent_runs`, `tool_calls`, `analysis_artifacts`) no duplican
  `organization_id` — se reconstruye vía `agent_run.analysis_id -> analysis.organization_id`,
  y el filtro de tenant real ocurre una sola vez, al resolver el `Analysis` padre en el
  router (`_get_visible_analysis`), no en cada tabla hija por separado.
- Ningún secreto (credenciales de `data_sources`, tokens) se guarda en texto plano. Usa el
  patrón `secret_ref` con cifrado a nivel de aplicación.
- Resultados grandes (filas de análisis, exports) se modelan como artefacto o referencia
  (`analysis_artifacts`), nunca como columna gigante dentro de una fila.
- Se mantiene la trazabilidad `analysis -> agent_run -> tool_calls -> artifacts` mediante
  claves foráneas explícitas, no relaciones implícitas.
- Todo cambio de esquema pasa por una migración Alembic generada y revisada a mano (ver
  skill `database-migration`) — nunca se edita el esquema directamente en la base de datos.
- El SQL generado por el agente no usa el ORM de la plataforma ni sus sesiones — corre
  sobre una conexión read-only separada, validada por el SQL validator.
