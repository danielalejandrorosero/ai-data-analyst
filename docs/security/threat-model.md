# Threat model — AI Data Analyst

> Basado en la sección 8 y 8.1 del [SRS](../SRS.md). Este documento organiza esos controles
> para uso operativo; no introduce amenazas ni controles nuevos que el SRS no contemple.

## Principio rector

> El modelo puede proponer; el software autoriza.

Ningún control crítico de seguridad depende del comportamiento del LLM. Los controles viven
fuera del prompt, en código determinístico revisable y testeable.

## Amenazas y controles (SRS 8.1)

| Amenaza | Riesgo | Control |
|---|---|---|
| Prompt injection en documento | El agente intenta ejecutar acciones no deseadas | Contexto no confiable + tools autorizadas externamente |
| SQL injection vía generación LLM | Consulta peligrosa | Parser + allowlist + DB read-only |
| Cross-tenant access | Filtración de datos | Tenant scoping obligatorio en backend y DB |
| Secret leakage | Credenciales expuestas | Secret manager/ref + redacción de logs |
| DoS por consultas pesadas | Worker/DB saturados | Timeout, límites, concurrency control |
| Carga maliciosa de archivo | Parser comprometido/consumo excesivo | Size limits, MIME validation, sandboxing |

## Controles obligatorios (SRS sección 8)

- [ ] Base de datos de solo lectura para consultas generadas por el agente.
- [ ] Parser/validator SQL que permita `SELECT` y expresiones explícitamente autorizadas.
- [ ] Bloqueo de DDL y DML en el camino de ejecución del agente.
- [ ] Timeout de consultas y máximo de filas retornadas.
- [ ] Rate limit por usuario y tenant.
- [ ] Separación de secretos, tokens y contexto del prompt.
- [ ] Sanitización de contenido proveniente de documentos no confiables.
- [ ] Auditoría de tool calls y decisiones críticas.
- [ ] Principio de mínimo privilegio para todos los servicios.

Cada casilla se marca cuando el control correspondiente tiene implementación **y** tests
negativos que intentan superarlo (ver `.claude/rules/testing.md` y `RNF-021`).

## Decisiones de implementación relacionadas

- Aislamiento multi-tenant: [`adr/0003-multi-tenant-isolation.md`](../adr/0003-multi-tenant-isolation.md)
- Gestión de secretos: [`adr/0004-secrets-management.md`](../adr/0004-secrets-management.md)
- Autenticación: [`adr/0002-auth-strategy.md`](../adr/0002-auth-strategy.md)

## Pendiente de completar (no en Fase 0)

Este documento se ampliará durante Fase 1 (auth) y Fase 3 (SQL seguro) con el detalle
concreto de implementación de cada control, a medida que exista código que auditar.

## Revisión Fase 1 + Fase 2 (2026-08-15)

Revisión adversarial de auth (registro/login/RBAC/tenant isolation) y datasets (import
CSV/Excel). Hallazgos corregidos: timing side-channel de enumeración de usuarios en login
(se agregó verificación Argon2id contra un hash dummy cuando el email no existe, para que
el tiempo de respuesta no delate si una cuenta existe), tamaño de archivo validado antes de
bufferizar todo a memoria, colisión de nombres de columna tras truncado a 63 chars, y una
condición de carrera en la creación del `data_source` de tipo "upload".

**Limitaciones conocidas, diferidas conscientemente** (no son bugs no vistos — se
evaluaron y se decidió no resolverlas todavía):

- **DoS por archivo Excel comprimido ("zip bomb")**: el límite de filas (`import_max_rows`)
  se valida recién después de que Polars parsea el `.xlsx` completo en memoria — un archivo
  pequeño y válido puede expandirse a un consumo de memoria/CPU grande antes del rechazo.
  Requiere lectura streaming/acotada o límites de memoria a nivel de proceso, no un fix
  puntual. Se revisita si el import deja de ser síncrono en el request (ver
  `docs/architecture.md` sección 12) o en Fase 8 (hardening).
- **Validación de tipo de archivo solo por extensión**, no por magic bytes/`Content-Type`
  real. Riesgo bajo hoy (Polars simplemente falla a parsear contenido no correspondiente),
  pero es una brecha de defensa en profundidad frente al control "MIME validation" que pide
  la fila "Carga maliciosa de archivo" de la tabla de arriba.
- **Rate limiting**: todavía no implementado en ningún endpoint (ni `/auth/login` ni
  `/datasets/import`). La fila "Rate limit por usuario y tenant" del SRS (sección 8) vive
  en el contexto de "Seguridad y controles de IA", por lo que se interpreta como prioritario
  para el canal del agente (Fase 3+) — pero su ausencia hoy también deja `/auth/login` sin
  protección contra fuerza bruta más allá del costo intrínseco de Argon2id. Evaluar agregar
  rate limiting básico de auth antes de Fase 8 si el proyecto se expone públicamente antes.
- **Intentos de login con email inexistente no se auditan**: `auth.login_failed` (RF-004)
  se registra cuando el usuario existe pero la password es incorrecta (scoped a sus
  organizaciones), pero un intento contra un email que no existe no tiene ningún tenant al
  que asociar el evento — `audit_events.organization_id` es obligatorio por diseño. Cerrar
  esto del todo requeriría un canal de auditoría no tenant-scoped (log de seguridad a nivel
  de plataforma, separado del audit log por organización), que no existe todavía — se
  revisita si se agrega observabilidad centralizada en Fase 7.
