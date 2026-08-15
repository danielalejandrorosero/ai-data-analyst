# ADR-0002: Estrategia de autenticación para el MVP

## Estado
Aceptado — 2026-08-15

## Contexto
RF-001 del SRS exige "autenticación segura mediante credenciales y/o OIDC según la
implementación elegida", delegando explícitamente la decisión a la implementación.

## Decisión
El MVP implementa autenticación por **credenciales + JWT propio**. OIDC queda como
extensión posterior, fuera del MVP.

## Justificación
- Evita depender de un Identity Provider externo para poder demostrar el flujo completo
  (RF-001 a RF-004, CU-01) de forma autocontenida en Docker Compose.
- Es la opción más simple que satisface RF-001 sin comprometer RNF-011 (HTTPS) ni
  RNF-012 (RBAC + tenant isolation).

## Consecuencias
- El modelo `users` incluye `password_hash` desde el inicio; el campo `oidc_id` (mencionado
  en el modelo de datos del SRS, sección 6) queda reservado para cuando se implemente OIDC.
- Añadir OIDC más adelante no debe requerir cambios en el modelo de roles/membership.
