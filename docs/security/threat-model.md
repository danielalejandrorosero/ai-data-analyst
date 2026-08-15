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
