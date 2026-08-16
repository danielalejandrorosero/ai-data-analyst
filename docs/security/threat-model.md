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
| DoS por multi-consulta sin límite (RF-022, Fase 4) | Un LLM en loop ejecuta consultas válidas indefinidamente, cada una pasando el resto de los controles por separado | `AGENT_MAX_QUERIES_PER_RUN` (default 5) — `execute_readonly_sql` rechaza pasado el tope, sin colgar el análisis |
| Carga maliciosa de archivo | Parser comprometido/consumo excesivo | Size limits, MIME validation, sandboxing |
| SSRF vía registro de conexión externa (RF-010) | El backend se usa como proxy para sondear la red interna del despliegue (otros contenedores, endpoints de metadata de nube) | Resolución DNS + rechazo de IPs privadas/loopback/link-local/reservadas antes de conectar, mensaje de error único (sin importar la causa), auditoría de intentos fallidos |

## Controles obligatorios (SRS sección 8)

- [x] Base de datos de solo lectura para consultas generadas por el agente. Rol Postgres
      `agent_readonly` sin permisos sobre `public` (Fase 3a) — probado con UPDATE/lectura
      cross-schema real bloqueados por permisos, no solo por el validator.
- [x] Parser/validator SQL que permita `SELECT` y expresiones explícitamente autorizadas.
      `domain/agent/sql_validator.py` (sqlglot), 25 tests unitarios.
- [x] Bloqueo de DDL y DML en el camino de ejecución del agente. Doble capa: validator +
      permisos del rol Postgres (defensa en profundidad, ver ADR y tests de `execution.py`).
- [x] Timeout de consultas y máximo de filas retornadas. `statement_timeout` a nivel Postgres
      + `LIMIT` inyectado en el propio SQL validado (no solo truncado post-hoc). Probado con
      un `pg_sleep` real cancelado por Postgres (`test_agent_execution.py::TestStatementTimeout`),
      no solo asumido por el código.
- [x] Límites de complejidad de la consulta (RF-032). El validador ya restringe a una única
      tabla física (más CTEs); además acota `JOIN`s y subqueries anidadas, configurable vía
      `AGENT_SQL_MAX_JOINS`/`AGENT_SQL_MAX_SUBQUERIES` (`sql_validator.py::_check_complexity`,
      con tests en `TestComplexityLimits`).
- [ ] Rate limit por usuario y tenant. Sigue sin implementar (ver nota abajo).
- [x] Separación de secretos, tokens y contexto del prompt. `LLM_API_KEY` nunca entra al
      system prompt ni al contexto del modelo — vive solo en config/provider.
- [ ] Sanitización de contenido proveniente de documentos no confiables. No aplica todavía
      (RAG documental es Fase 6).
- [x] Auditoría de tool calls y decisiones críticas. Cada tool call queda en `tool_calls`
      (RF-023/RF-033); intento de leer tabla ajena queda registrado como `ERROR` sin
      ejecutarse (ver `test_agent_orchestrator.py::TestOrchestratorBlocksTenantCrossover`).
      Nota: esto vive en `tool_calls`/`agent_runs`, no en `audit_events` (que queda reservado
      a decisiones de auth/RBAC/tenant) — ver `.claude/rules/security.md`.
- [ ] Principio de mínimo privilegio para todos los servicios. Parcial: `agent_readonly` lo
      cumple; no es un checkbox de una sola implementación, es un principio transversal que
      se sigue revisando fase a fase.

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
  **Fase 4 agrava esto**: `GET /analyses/{id}/events` (SSE) abre una conexión persistente +
  una suscripción Redis por request, sin límite de conexiones concurrentes por usuario — un
  recurso más caro por request que los endpoints REST normales. Mismo gap ya conocido, pero
  ahora con mayor impacto potencial si se expone públicamente sin resolverlo antes.
- **SSRF: queda un canal de timing residual, no de contenido**. El guard (RF-010,
  `domain/datasets/connections.py::_assert_host_is_not_internal`) rechaza rangos privados/
  loopback/link-local/reservados con el mismo mensaje genérico que cualquier otro fallo, así
  que el *contenido* de la respuesta nunca distingue la causa. Pero el rechazo por rango
  bloqueado es prácticamente instantáneo (resolución DNS + aritmética de IP, sin intento de
  conexión TCP), mientras que un host externo real que no responde tarda hasta
  `CONNECTION_TEST_TIMEOUT_SECONDS`. Un atacante que mida *latencia* (no solo la respuesta)
  puede inferir "está en el rango bloqueado" vs. "es un host externo real que no contestó" —
  no permite mapear qué host interno específico existe, sólo que el rango sí es tratado como
  interno. No se corrigió con normalización de tiempos (delay artificial) por ser
  desproporcionado para el nivel de amenaza de este MVP; revisitar si el proyecto se expone
  públicamente antes de Fase 8.
- **MySQL (RF-010) diferido**: el SRS pide registrar conexiones PostgreSQL y MySQL; se
  implementó solo PostgreSQL (`POST /api/v1/datasets/connections`, Fase 3b) — MySQL
  requiere una dependencia async nueva y su propio servicio de DB para testearlo con una
  instancia real, no mocks (`.claude/rules/testing.md`). El schema de request rechaza
  `type: "mysql"` explícitamente (422) en vez de aceptarlo y fallar más adelante.
- **Conexiones externas registradas todavía no las usa el agente**: RF-010 cubre solo el
  registro (credenciales validadas y cifradas). El agente sigue ejecutando SQL únicamente
  contra datasets importados (Fase 2/3a) — conectar el agente a estas fuentes externas es
  trabajo no iniciado, sin ninguna de las capas de seguridad de Fase 3a (validator,
  `agent_readonly`) todavía aplicadas a ellas.
- **Intentos de login con email inexistente no se auditan**: `auth.login_failed` (RF-004)
  se registra cuando el usuario existe pero la password es incorrecta (scoped a sus
  organizaciones), pero un intento contra un email que no existe no tiene ningún tenant al
  que asociar el evento — `audit_events.organization_id` es obligatorio por diseño. Cerrar
  esto del todo requeriría un canal de auditoría no tenant-scoped (log de seguridad a nivel
  de plataforma, separado del audit log por organización), que no existe todavía — se
  revisita si se agrega observabilidad centralizada en Fase 7.
