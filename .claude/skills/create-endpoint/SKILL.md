---
name: create-endpoint
description: Scaffolds a new FastAPI /api/v1 endpoint (router, Pydantic schema, service call, RBAC/tenant check, test skeleton) following this project's backend conventions.
---

# create-endpoint

Crea un endpoint nuevo bajo `/api/v1` siguiendo las convenciones de `backend/CLAUDE.md` y
`.claude/rules/backend.md`.

## Cuándo usarla
Al añadir cualquier endpoint nuevo a la API (no para modificar uno existente de forma trivial).

## Qué debe garantizar
1. Ruta bajo `/api/v1/...`, con versión explícita si rompe compatibilidad (RNF-023).
2. Schema Pydantic v2 de request/response, sin reutilizar modelos SQLAlchemy directamente
   como contrato de API.
3. Validación explícita de rol (OWNER/ADMIN/ANALYST/VIEWER) y `organization_id` antes de
   tocar datos — nunca delegarlo al frontend.
4. Llamada a la capa de servicio de dominio correspondiente, no lógica de negocio en el
   router.
5. Esqueleto de test (unit y/o integración) que cubra al menos un caso autorizado y un
   caso de acceso cruzado de tenant/rol rechazado.

## Qué NO hace
No implementa lógica de negocio de fases futuras ni inventa endpoints que no estén en
`docs/SRS.md` (sección 7) o explícitamente aprobados en la conversación con el usuario.
