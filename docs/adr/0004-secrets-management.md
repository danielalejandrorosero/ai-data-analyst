# ADR-0004: Gestión de secretos para el MVP

## Estado
Aceptado — 2026-08-15

## Contexto
RNF-010 exige que credenciales y secretos no se almacenen en texto plano en tablas de
negocio ni logs. La sección 8 del SRS menciona "secret manager/ref" sin fijar tecnología.

## Decisión
El MVP usa **cifrado a nivel de aplicación** (envelope encryption) sobre la columna
`data_sources.secret_ref`, con la clave de cifrado provista por la variable de entorno
`SECRET_ENCRYPTION_KEY`. Un secret manager externo (Vault, AWS Secrets Manager, etc.)
queda como mejora de hardening (Fase 8), no como dependencia del MVP.

## Justificación
- Cumple RNF-010 (nada en texto plano) sin requerir un servicio adicional en Docker Compose.
- Consistente con el despliegue inicial en VM/servidor administrado que describe la
  sección 11 del SRS — introducir un secret manager externo antes de tener producción
  real sería complejidad prematura.

## Consecuencias
- `SECRET_ENCRYPTION_KEY` debe rotar de forma controlada; su ausencia o cambio invalida
  los secretos ya cifrados — esto debe documentarse en la guía de despliegue.
- Migrar a un secret manager externo más adelante implica cambiar la implementación detrás
  de `secret_ref`, no el modelo de datos.
