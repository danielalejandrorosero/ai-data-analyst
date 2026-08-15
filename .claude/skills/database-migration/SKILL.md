---
name: database-migration
description: Wraps Alembic revision creation for this project with a checklist (tenant scoping, reversibility, secret handling) before it's considered ready.
---

# database-migration

Genera y revisa una migración Alembic para cambios en el modelo de datos (`docs/SRS.md`
sección 6).

## Cuándo usarla
Al agregar, modificar o eliminar una tabla/columna del modelo de la plataforma.

## Checklist antes de dar la migración por lista
1. ¿La tabla nueva con datos de negocio tiene `organization_id`? (aislamiento multi-tenant,
   ver `docs/adr/0003-multi-tenant-isolation.md`)
2. ¿Es reversible (`downgrade` funcional), o si no lo es, está justificado y advertido?
3. ¿Algún campo nuevo podría contener un secreto? Si sí, debe seguir el patrón
   `secret_ref` (`docs/adr/0004-secrets-management.md`), nunca texto plano.
4. ¿Los resultados grandes se modelan como artefacto/referencia y no como columna gigante
   en una sola fila? (principio de persistencia, SRS sección 6.1)
5. ¿La migración fue generada contra el modelo actual (`alembic revision --autogenerate`)
   y revisada a mano, no aceptada ciegamente?

## Qué NO hace
No ejecuta migraciones destructivas (`DROP TABLE`, `DROP COLUMN` con pérdida de datos) sin
confirmación explícita del usuario.
