# Arquitectura — AI Data Analyst

> Este documento describe **cómo** se construye el sistema descrito en [`SRS.md`](./SRS.md).
> El **qué** debe hacer el sistema vive en el SRS. El **por qué** de decisiones técnicas
> individuales vive en [`adr/`](./adr/). Si una afirmación aquí contradice al SRS, el SRS manda.

## 1. Visión general

Monolito modular en Python, siguiendo la arquitectura de referencia del SRS (sección 5):

- **`frontend/`** — React + TypeScript + Vite. Consume la API vía HTTPS y el stream de eventos vía SSE.
- **`backend/`** — FastAPI + Pydantic v2. Expone `/api`, gestiona auth/RBAC/tenant scoping,
  valida y ejecuta SQL read-only, coordina el agente y sirve SSE.
- **`workers/`** — ARQ sobre Redis. Ejecuta jobs asíncronos: import de datasets y el ciclo de vida
  completo del agente (`QUEUED -> ... -> COMPLETED/FAILED/CANCELLED/TIMED_OUT`).
- **`infrastructure/`** — Docker Compose, Prometheus, Grafana, reverse proxy.
- **PostgreSQL** (+ pgvector) como única base de datos de la plataforma.
- **Redis** como broker de la cola ARQ y canal de publicación de eventos de progreso.

```
Usuario -> React (frontend/) -> FastAPI (backend/) -> encola job ARQ
                                     |                        |
                                     |                    workers/
                                     |                        |
                                     |                 Agent Orchestrator
                                     |                        |
                                     |      +-----------------+------------------+
                                     |      |                 |                  |
                                     |  Schema Tool       SQL Tool         Analysis Tool
                                     |      |                 |                  |
                                     |      +-----------------+------------------+
                                     |                        |
                                     |                   PostgreSQL
                                     |                        |
                                     |              eventos de progreso
                                     |                        |
                                     +<----------------- Redis pub/sub
                                     |
                              FastAPI SSE
                                     |
                                React UI
```

## 2. Por qué monolito modular (no microservicios)

El SRS (secciones 5 y 18) exige evitar microservicios prematuros. `backend/` y `workers/`
comparten el mismo código Python (modelos SQLAlchemy, servicios de dominio, SQL validator,
definición de agent tools) importado directamente — no existe un paquete `shared-contracts`
separado. Ver [`adr/0001-monorepo-structure.md`](./adr/0001-monorepo-structure.md).

En la práctica esto se implementa con un **uv workspace** en la raíz del repo: `backend/` y
`workers/` son miembros del mismo workspace, comparten un único `uv.lock` y un único
`.venv`, y `workers` declara `backend` como dependencia editable del workspace. El paquete
instalable de `backend/` se llama `app`; el de `workers/` se llama `tasks` (no `app`,
porque dos paquetes no pueden instalarse con el mismo nombre de módulo top-level en el
mismo entorno) — así, código en `workers/tasks/*` hace `from app.domain... import ...`
directamente.

## 3. Estructura del repositorio

```
ai-data-analyst/
├── backend/     # API, dominio, agente, SQL validator, modelos DB (FastAPI)
├── workers/     # Jobs ARQ: import de datasets, ejecución del agente
├── frontend/    # UI React
├── infrastructure/ # Docker, Prometheus, Grafana, reverse proxy
├── docs/        # Este árbol de documentación
└── .claude/     # Reglas, skills y agentes para trabajar con Claude Code
```

Detalle interno de cada app (routers, servicios, modelos, componentes) se define en Fase 0.1
cuando se agregue el scaffolding real de cada aplicación — no forma parte de esta primera
pasada de estructura/documentación.

## 4. Flujo de una ejecución de análisis

1. Cliente hace `POST /api/analyses` con `dataset_id` y `question`.
2. `backend/` valida RBAC + tenant, crea el registro `analyses` (estado `QUEUED`) y encola un job ARQ.
3. `workers/` toma el job, instancia el agente y transiciona el estado (`PLANNING -> TOOL_RUNNING -> ANALYZING -> GENERATING_RESPONSE`).
4. Cada tool call (`inspect_schema`, `execute_readonly_sql`, `run_analysis`, `create_chart`,
   `search_documents`) se registra en `tool_calls` y publica un evento de progreso en Redis.
5. `backend/` expone `GET /api/analyses/{id}/events` como stream SSE que retransmite esos eventos al cliente.
6. Al finalizar, el resultado queda en `analysis_artifacts`; el estado final es `COMPLETED`,
   `FAILED`, `CANCELLED` o `TIMED_OUT`.

## 5. Aislamiento multi-tenant

Decisión para el MVP (ver [`adr/0003-multi-tenant-isolation.md`](./adr/0003-multi-tenant-isolation.md)):

- Todo modelo con datos de negocio tiene `organization_id`.
- El filtrado por tenant ocurre en la capa de servicio de dominio (`backend/app/domain/*`),
  nunca delegado únicamente al router ni confiado al cliente.
- PostgreSQL Row-Level Security queda como capa de defensa adicional para hardening (Fase 8),
  no como dependencia del MVP.

## 6. Autenticación

Decisión para el MVP (ver [`adr/0002-auth-strategy.md`](./adr/0002-auth-strategy.md)):
credenciales + JWT propio. OIDC queda como extensión posterior, sin bloquear el MVP.

## 7. Gestión de secretos

Decisión para el MVP (ver [`adr/0004-secrets-management.md`](./adr/0004-secrets-management.md)):
cifrado a nivel de aplicación sobre `data_sources.secret_ref` (envelope encryption con clave en
variable de entorno). Un secret manager externo (Vault, AWS Secrets Manager, etc.) queda como
mejora de hardening, no como dependencia del MVP.

## 8. SQL seguro (implementado desde Fase 3a)

- El agente nunca usa la sesión ORM de la plataforma para ejecutar SQL generado — usa un
  engine SQLAlchemy separado (`domain/agent/execution.py`) contra `AGENT_DATABASE_URL`, con
  el rol Postgres **`agent_readonly`** (creado en
  `infrastructure/postgres/init/002-agent-readonly-role.sh`): `SELECT`-only sobre el schema
  `datasets`, sin ningún permiso sobre `public` (donde viven las tablas de la plataforma).
  Esto es una segunda capa de defensa independiente del validador — probado directamente
  (un `UPDATE` o una lectura de `public.users` con SQL sintácticamente válido son rechazados
  por Postgres mismo, no solo por la app).
- Toda consulta del agente pasa por `domain/agent/sql_validator.py` (parser real con
  `sqlglot`, no regex): una sola sentencia `SELECT`, sin `SELECT INTO`, y solo puede
  referenciar la tabla física exacta del dataset autorizado (ni siquiera otro dataset de la
  misma organización — aislamiento de tenant también a nivel SQL, no solo a nivel API).
- Límite de filas (RF-032): el validador inyecta `LIMIT max_rows + 1` en el propio SQL antes
  de ejecutarlo — Postgres nunca calcula más filas de las necesarias, no se trunca después
  de traer todo.
- Timeout (RNF-003): `statement_timeout` fijado a nivel de conexión Postgres, no solo un
  timeout de Python alrededor de la llamada.
- Límites de complejidad (RF-032): además de timeout y límite de filas, el validador acota
  cantidad de `JOIN`s y de subqueries anidadas (`AGENT_SQL_MAX_JOINS`/
  `AGENT_SQL_MAX_SUBQUERIES`) — el resto de la superficie de "complejidad" ya está cerrada
  por el allowlist de una única tabla física.
- Primer agente (`domain/agent/orchestrator.py`, PydanticAI): tools `inspect_schema` +
  `execute_readonly_sql`, cada tool call queda en `tool_calls` con duración, hash del input
  y resumen del resultado (RF-023, RF-033). Proveedor de LLM: Kimi (Moonshot AI) vía API
  compatible con OpenAI — ver `docs/adr/0009-llm-provider.md`.
- `POST /api/analyses` (Fase 4) encola el análisis como job real de `workers/` (ARQ) y
  responde `202` de inmediato en `QUEUED` — ya no corre sincrónico dentro del request como
  en Fase 3a. Nota: `POST /datasets/import` (sección 12) sigue siendo sincrónico — esa
  decisión no cambió, solo la de `analyses`. El cliente sigue el progreso vía
  `GET /analyses/{id}` (polling) o `GET /analyses/{id}/events` (SSE real, sección 8.2).
  **Decisión consciente sobre RNF-023** ("cambio incompatible incrementa versión o crea
  ruta nueva"): este cambio (`201`+resultado síncrono → `202`+`QUEUED`, y `result` de `dict`
  a `list[dict]`) es incompatible sobre una ruta ya existente, sin nueva versión. Se decide
  así porque no hay ningún consumidor real todavía (`frontend/` no tiene scaffolding) — el
  costo de romper compatibilidad es cero hoy. Si esto se repite después de que exista un
  cliente real, hay que versionar de verdad.

### 8.2 Multi-paso, cancelación y progreso en vivo (RF-022/RF-025, Fase 4)

- El agente puede ejecutar más de una consulta por pregunta compleja (RF-022) —
  `AgentDeps.results` acumula la evidencia de cada consulta exitosa (no se pisan entre sí),
  con un tope configurable (`AGENT_MAX_QUERIES_PER_RUN`, default 5) para no convertir esto
  en un vector de costo/DoS nuevo — un LLM en loop sin ese límite podría generar consultas
  válidas indefinidamente, cada una pasando el resto de los controles por separado. El
  chequeo del tope es sincrónico (sin ningún `await` antes de reservar el cupo en
  `AgentDeps.query_count`) — pydantic-ai puede ejecutar varias tool calls del mismo turno en
  paralelo por default (comportamiento estándar de function-calling, no requiere prompt
  injection), así que un chequeo basado en `len(results)` (que solo crece después del
  round-trip a Postgres) sería una condición de carrera real, no solo teórica — confirmado
  con un test que emite 20 tool calls en un único turno. `execute_readonly_sql` además se
  registra con `sequential=True` en pydantic-ai como segunda capa, no la única.
- Las filas guardadas como evidencia en `Analysis.result_json` se acotan a 100 por consulta
  (`_EVIDENCE_ROW_CAP` en `tools.py`), no las hasta 5000 que la consulta puede leer — RF-022
  permite hasta 5 consultas por análisis, así que sin este tope la columna JSONB podría
  crecer a ~25.000 filas en una sola fila de `analyses`, violando
  `.claude/rules/database.md` ("nunca como columna gigante dentro de una fila"). El acceso
  al resultado completo/exportable es RF-042 (`analysis_artifacts`, Fase 5) — todavía no
  implementado; esto es evidencia suficiente para sustentar la respuesta, no un export.
- `POST /api/analyses/{id}/cancel` (RF-025) usa `arq.jobs.Job.abort()`. Dos detalles
  encontrados solo probando contra Docker real, no obvios por la documentación de arq:
  - El `WorkerSettings` necesita `allow_abort_jobs = True` — sin eso, `Job.abort()` no
    interrumpe un job que ya está corriendo, solo lo saca de la cola si todavía no arrancó.
  - Si arq aborta el job ANTES de que el worker lo arranque ("aborted before start"),
    `run_analysis()` nunca llega a ejecutarse — nada dentro de `domain/agent/orchestrator.py`
    deja el `Analysis` en `CANCELLED`. El endpoint de cancelación mismo fuerza esa
    transición cuando `job.abort()` confirma que abortó y el análisis sigue en un estado no
    terminal — sin esto, quedaba colgado en `QUEUED` para siempre.
  - Cuando el job SÍ estaba corriendo, la cancelación llega como `asyncio.CancelledError`
    dentro de `run_analysis` (una `BaseException`, no `Exception` — no la captura el except
    genérico de errores inesperados) — se deja el `Analysis`/`AgentRun` en `CANCELLED` y se
    re-lanza, para que arq registre el job como abortado.
- Progreso en vivo: `domain/agent/events.py::publish_event` publica a Redis pub/sub
  (`analysis:{id}:events`) en cada transición de estado y cada tool call; el endpoint SSE
  se suscribe y retransmite. Es best-effort — si Redis falla, no tumba el análisis; la
  fuente de verdad sigue siendo Postgres vía `GET /analyses/{id}`.

## 8.1 Conexiones externas (RF-010, Fase 3b)

- `POST /api/datasets/connections` (rol OWNER/ADMIN) registra una conexión PostgreSQL
  externa: primero se prueba con un `SELECT 1` controlado (`domain/datasets/connections.py`,
  timeout corto y fijo) — si falla, no se persiste nada, ni siquiera cifrado. Solo si la
  prueba pasa se guarda la fila en `data_sources` (tipo `postgres`), con `host`/`port`/
  `database_name`/`username` en columnas planas (necesarias para catálogo/UI) y la
  `password` cifrada (Fernet, clave derivada de `SECRET_ENCRYPTION_KEY`) en `secret_ref` —
  nunca en texto plano, ver `docs/adr/0004-secrets-management.md`.
- Defensa SSRF: antes de intentar cualquier conexión, se resuelve el `host` por DNS y se
  rechaza si alguna IP resuelta cae en un rango privado/loopback/link-local/reservado — sin
  esto, el endpoint sería una primitiva para usar el propio backend como proxy hacia la red
  interna del despliegue. El DSN se arma con `sqlalchemy.engine.URL.create(...)` (no
  f-string manual) para que caracteres especiales en usuario/password no corrompan el
  parseo del host. Ver `docs/security/threat-model.md` para el detalle de amenaza y la
  limitación de timing residual conocida.
- **MySQL queda deliberadamente diferido**: el SRS (RF-010) pide ambos motores, pero
  soportar MySQL implica una dependencia async nueva (driver) y su propio servicio de
  base de datos para poder testearlo contra una instancia real (regla de testing del
  proyecto — no mocks). Se decidió no construir esa infraestructura hasta que haya una
  necesidad concreta. El schema Pydantic (`ExternalConnectionCreateRequest.type`) solo
  acepta `"postgres"` por ahora — un intento de `"mysql"` falla la validación del request
  (422), no queda a medio implementar.
- Una única conexión externa por (organización, tipo) — mismo `UniqueConstraint` que ya
  existía para la fila `"upload"` de Fase 2. El SRS no pide múltiples conexiones del mismo
  motor por organización; registrar de nuevo actualiza (reemplaza) la conexión existente.
- Estas conexiones **todavía no están conectadas al agente** — el agente sigue operando
  solo sobre datasets importados (Fase 2/3a). Ejecutar SQL del agente contra una fuente
  externa registrada acá es trabajo pendiente, no incluido en este alcance.

## 8.3 Análisis y visualización (RF-040 a RF-043, Fase 5)

- Dos tools nuevas del agente, ambas registradas con `sequential=True` (mismo motivo que
  `execute_readonly_sql` — evita que tool calls paralelas del modelo rompan un presupuesto
  compartido):
  - `run_analysis` (RF-040): post-procesa con Polars el resultado de la última operación
    exitosa (group_by/agg/sort/limit) — no ejecuta SQL nuevo. Funciones de agregación
    restringidas a un allowlist (`sum`/`mean`/`min`/`max`/`count`), nunca `eval`/`exec` de
    código del modelo. Comparte presupuesto (`AGENT_MAX_QUERIES_PER_RUN`) con
    `execute_readonly_sql` — un post-proceso Polars sigue siendo trabajo que un LLM en loop
    podría repetir sin límite si no contara para el mismo tope.
  - `create_chart` (RF-041): genera una especificación de gráfico (tipo, ejes, datos) — no
    una imagen — persistida en `analysis_artifacts`, con su propio tope
    (`AGENT_MAX_CHARTS_PER_RUN`).
- **`AgentDeps.results` vs `AgentDeps.last_full_result`** (`domain/agent/deps.py`): lo que se
  persiste en `Analysis.result_json` está acotado a 100 filas por operación
  (`_EVIDENCE_ROW_CAP`, para no dejar una columna JSONB gigante — `.claude/rules/database.md`).
  Encontrado en revisión de seguridad: `run_analysis`/`create_chart` inicialmente leían de
  esa misma muestra acotada, así que una agregación sobre una consulta de, por ejemplo, 3000
  filas calculaba sobre las primeras 100 — un resultado con apariencia correcta pero
  matemáticamente equivocado, sin ningún indicio de ser parcial. Se corrigió separando un
  buffer de trabajo efímero (`last_full_result`, hasta `max_rows`, nunca persistido tal cual)
  del que ambas tools leen, del array de evidencia persistida (acotado, para
  `Analysis.result_json`). `create_chart` marca `spec_json["data_truncated"]` explícitamente
  cuando el gráfico es una muestra del resultado completo.
- RF-042 (trazabilidad): `analysis_artifacts.source_sql` referencia la consulta que originó
  el gráfico — `GET /analyses/{id}/artifacts`. La tabla no tiene `organization_id` propio
  (mismo patrón que `agent_runs`/`tool_calls` — ver excepción documentada en
  `.claude/rules/database.md`), el aislamiento de tenant ocurre una sola vez al resolver el
  `Analysis` padre en el router.
- RF-043 (export): `GET /analyses/{id}/export?format=csv|json&query_index=N` sirve una de las
  evidencias de `result_json` (la última por defecto) como archivo descargable. Mismo
  chequeo de membership que el resto de los endpoints de detalle.
- **Bug real encontrado probando contra Docker con datos reales**: `SUM()`/`AVG()` sobre una
  columna entera devuelve `numeric` en Postgres (para evitar overflow), que asyncpg decodifica
  como `Decimal` — `json.dumps` no lo serializa. Se normaliza en el único punto donde las
  filas salen de Postgres (`domain/agent/execution.py::_json_safe`, también cubre columnas
  Date/DateTime), para que nada río abajo tenga que repetir el chequeo.

## 9. Observabilidad

OpenTelemetry instrumenta `backend/` y `workers/`; las métricas se exponen para Prometheus y
se visualizan en Grafana (definiciones versionadas en `infrastructure/`). Cada análisis es
trazable de punta a punta mediante `trace_id` (ver sección 9 del SRS para el detalle de métricas).

## 10. Tooling

- Backend / workers: Python 3.13 gestionado con **uv**.
- Frontend: **pnpm**.
- Justificación en [`adr/0005-tooling.md`](./adr/0005-tooling.md).

## 11. RAG documental (Fase 6)

Especificado en SRS sección 3.7 (RF-060 a RF-065, agregados 2026-08-16 — este documento
exigía escribirlos antes de implementar, y así se hizo).

Diseño:

- **Modelo de datos**: `documents` (por organización, con `status`
  PROCESSING/READY/FAILED) y `document_chunks` (FK `ON DELETE CASCADE`, texto del
  fragmento + `embedding vector(384)`). Los chunks no duplican `organization_id` — el
  filtro de tenant ocurre al resolver el documento padre, misma excepción aceptada que
  las tablas hijas de `analyses` (`.claude/rules/database.md`).
- **Ingesta asíncrona**: la subida crea el documento en PROCESSING y encola un job ARQ
  (`workers/`); el worker extrae texto (pypdf / python-docx / decodificación directa),
  fragmenta por párrafos con solapamiento, embebe localmente
  (`adr/0011-local-embeddings.md`) y deja el documento en READY o FAILED — nunca colgado.
- **Búsqueda híbrida** (RF-062): top-k por similitud coseno en pgvector + top-k por
  full-text de Postgres, fusionados con Reciprocal Rank Fusion. Expuesta en la API para
  la UI y como tool `search_documents` del agente (RF-063), auditada en `tool_calls`.
- **RNF-015 / RF-064**: los fragmentos recuperados se inyectan al agente delimitados y
  marcados explícitamente como datos no confiables; ninguna instrucción embebida en un
  documento pasa a formar parte de las políticas del agente (las tools autorizadas y sus
  límites viven en el backend, no en el prompt).

## 12. Datasets: tablas físicas dinámicas (fuera del ciclo de vida de Alembic)

Cada dataset importado (RF-011) crea una **tabla Postgres real** en el schema `datasets`
(separado de `public`, donde viven las tablas de la plataforma), con columnas inferidas del
CSV/Excel — ver `backend/app/domain/datasets/service.py`. Esto es una excepción deliberada a
la regla general (`.claude/rules/database.md`: "todo cambio de esquema pasa por una migración
Alembic"): el esquema de esas tablas es arbitrario y decidido en runtime por el archivo que
sube cada usuario, no algo que tenga sentido versionar como schema de la plataforma.

Consecuencias a tener presentes:

- `alembic downgrade` de la migración de `datasets`/`data_sources` borra solo el **catálogo**
  (`public.datasets`, `public.data_sources`) — nunca toca el schema `datasets` ni sus tablas
  físicas, porque Alembic no sabe que existen. Un `downgrade base` no deja la base de datos en
  un estado realmente pristino si hay datasets importados.
- Cuando exista borrado de datasets (todavía no implementado), debe borrar la fila de catálogo
  **y** hacer `DROP TABLE datasets.ds_<id>` de forma atómica, en la misma transacción — mismo
  patrón que ya usa `import_file` para crear ambas cosas juntas.
- La creación de la tabla física ocurre en la misma transacción de sesión que el insert del
  catálogo y el `audit_event` (ver `service.py`, `conn = await db.connection()`), así que un
  fallo a mitad de camino no deja tablas huérfanas — pero esto es válido para la ruta de
  *creación*, no para el rollback de Alembic descrito arriba.

**Divergencia conocida con el diagrama de la sección 1**: el diagrama y la sección 4 describen
el import de datasets como un job de `workers/` (ARQ). La implementación actual de Fase 2
ejecuta el import **de forma síncrona dentro del propio request HTTP** (`POST
/api/datasets/import` lee, parsea e inserta todo antes de responder) — es una simplificación
consciente para el MVP de Fase 2, no un error. Si `import_max_rows` (200k por defecto) empieza
a generar timeouts de request reales, mover el import a un job de `workers/` (con polling o
notificación de estado) es el rediseño esperado — no antes, para no construir infraestructura
async sin una necesidad concreta todavía medida.
