# ADR-0003: Mecanismo de aislamiento multi-tenant para el MVP

## Estado
Aceptado — 2026-08-15

## Contexto
RF-003 y RNF-012 del SRS exigen aislamiento de recursos por organización/tenant "obligatorio"
en cada operación protegida, sin especificar el mecanismo técnico.

## Decisión
El MVP aplica el aislamiento mediante **filtrado por `organization_id` en la capa de
servicio de dominio** (`backend/app/domain/*`), consistente entre `backend/` y `workers/`.
PostgreSQL Row-Level Security (RLS) queda como capa de defensa adicional para hardening
(Fase 8), no como dependencia del MVP.

## Justificación
- Es el mecanismo más simple que cumple RNF-012 sin requerir gestión adicional de roles
  de base de datos ni políticas RLS desde el día uno — alineado con "complejidad mínima".
- RLS aporta valor real como defensa en profundidad, pero introducir su complejidad
  operativa antes de tener el modelo de dominio estable sería prematuro.

## Consecuencias
- Todo modelo con datos de negocio debe declarar `organization_id` y todo query de dominio
  debe filtrarlo explícitamente — esto se refuerza en `.claude/rules/database.md`.
- Las pruebas negativas de acceso cruzado (RNF-012) deben cubrir la capa de servicio.
- Si se adopta RLS en Fase 8, no debería requerir cambios de esquema, solo políticas
  adicionales sobre las tablas existentes.
