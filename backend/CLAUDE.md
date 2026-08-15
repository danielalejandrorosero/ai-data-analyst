# backend/ — CLAUDE.md

Servicios de dominio desacoplados: auth, datasets, analysis, agent, audit, observability.
FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic. Gestionado con **uv**.

## Reglas específicas
- Toda ruta nueva va bajo `/api/v1/...`; un cambio incompatible crea nueva versión, no
  modifica el contrato existente (RNF-023).
- Todo endpoint protegido valida rol (OWNER/ADMIN/ANALYST/VIEWER) y `organization_id` —
  nunca confiar solo en el frontend.
- El SQL del agente nunca pasa por el ORM de la plataforma ni reutiliza sesiones con
  permisos de escritura: usa el validator + credenciales read-only dedicadas.
- Cambios de modelo de datos van vía migración Alembic, nunca se edita el schema a mano.
- Los dominios no importan routers de otros dominios directamente — comunicación vía capa
  de servicio.
- Todo tool call del agente y toda decisión de autorización se audita (`audit_events`).
- Tests unitarios obligatorios para: SQL validator, RBAC, tenant scoping, agent tools.

Ver también `.claude/rules/backend.md`, `.claude/rules/security.md`,
`.claude/rules/database.md`, `.claude/rules/ai-agent.md`.
