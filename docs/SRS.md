# SRS — AI Data Analyst

**Especificación de Requisitos de Software**

| Campo | Valor |
|---|---|
| Documento | SRS-ADA-001 |
| Versión | 1.0 |
| Estado | Baseline para desarrollo |
| Fecha | 15 de agosto de 2026 |
| Producto | AI Data Analyst |
| Tipo | Plataforma web de análisis de datos asistido por agentes de IA |
| Autor | Daniel Alejandro Rosero Ortiz |
| Stack base | React + TypeScript / FastAPI + Python / PostgreSQL / Redis / Polars / Docker |

**Propósito**: servir como guía técnica y funcional para construir un único proyecto de portafolio de nivel profesional, orientado a Backend Engineering y AI Engineering.

> **Nota de este repositorio**: este archivo es la fuente de verdad **funcional** del proyecto (transcripción fiel de `SRS_AI_Data_Analyst.docx`, versión 1.0). Las decisiones de **cómo** se construye el sistema viven en [`architecture.md`](./architecture.md); el **por qué** de decisiones técnicas relevantes vive en [`adr/`](./adr/). Este documento no debe convertirse en un registro de decisiones de implementación — ver regla de cambio al final.

---

## 1. Introducción

Este documento define los requisitos, restricciones, criterios de aceptación, arquitectura de referencia y estrategia de implementación para AI Data Analyst. La plataforma permitirá que un usuario consulte y explore datos empresariales mediante lenguaje natural, mientras un agente de IA inspecciona esquemas, genera y valida consultas SQL de solo lectura, ejecuta análisis, produce visualizaciones y explica hallazgos con trazabilidad.

El documento está pensado para ser ejecutado como una especificación viva: durante el desarrollo podrá evolucionar, pero cualquier cambio relevante debe actualizar el ID del requisito, su estado y su criterio de aceptación.

### 1.1 Objetivos del producto

- Permitir preguntas de negocio sobre datos sin exigir conocimiento de SQL al usuario final.
- Usar IA de forma controlada: el modelo propone acciones, pero el sistema aplica permisos y validaciones fuera del modelo.
- Generar respuestas sustentadas por consultas y evidencia verificable.
- Convertir resultados analíticos en tablas y gráficos útiles para toma de decisiones.
- Ofrecer una base arquitectónica de producción: autenticación, RBAC, auditoría, observabilidad, pruebas, contenedores y CI/CD.
- Servir como proyecto de portafolio que demuestre dominio práctico de Backend, AI, Data Engineering y DevOps.

### 1.2 Alcance

El alcance inicial incluye conexión controlada a fuentes de datos relacionales, carga de CSV/Excel, catálogo de datasets, ejecución de análisis mediante agentes, consultas SQL de solo lectura, generación de gráficos, historial de análisis, autenticación, roles, auditoría, métricas y trazas.

Quedan fuera del MVP las mutaciones sobre bases de datos fuente, administración completa de ERPs/CRMs, entrenamiento de modelos propios, reemplazo de plataformas BI empresariales y despliegues multi-cloud complejos.

### 1.3 Stakeholders

| Rol | Interés |
|---|---|
| Owner | Configura la organización, fuentes de datos, usuarios y políticas. |
| Admin | Administra usuarios, conexiones y permisos delegados. |
| Analyst | Realiza consultas y análisis, crea y comparte resultados. |
| Viewer | Consulta análisis y dashboards permitidos, sin ejecutar acciones sensibles. |
| Desarrollador | Mantiene el producto, API, agentes, seguridad, pruebas e infraestructura. |

---

## 2. Descripción general del sistema

AI Data Analyst será una aplicación web multiusuario con frontend React/TypeScript y backend FastAPI/Python. El backend expondrá la API bajo `/api` (ver RNF-023), administrará autenticación y autorización, coordinará agentes de IA, ejecutará consultas en modo seguro y procesará datos con Polars cuando el análisis requiera operaciones fuera del motor SQL.

### 2.1 Flujo principal

```
Usuario -> React -> FastAPI -> Agent Orchestrator
                                      |
                       +--------------+--------------+
                       |              |               |
                  Schema Tool     SQL Tool      Analysis Tool
                       |              |               |
                       +--------------+--------------+
                                      |
                                 PostgreSQL
                                      |
                            Resultado/Evidencia
                                      |
                              FastAPI SSE
                                      |
                                React UI
```

### 2.2 Casos de uso principales

| ID | Caso de uso | Actor principal | Resultado |
|---|---|---|---|
| CU-01 | Registrarse/iniciar sesión | Todos | Sesión autenticada |
| CU-02 | Crear organización/proyecto | Owner | Tenant operativo |
| CU-03 | Registrar fuente de datos | Owner/Admin | Conexión validada y cifrada |
| CU-04 | Cargar CSV/Excel | Analyst/Admin | Dataset disponible para consulta |
| CU-05 | Preguntar a los datos | Analyst | Análisis ejecutado y respuesta sustentada |
| CU-06 | Inspeccionar ejecución | Analyst/Viewer | Progreso, herramientas y resultado |
| CU-07 | Generar visualización | Analyst | Gráfico asociado al análisis |
| CU-08 | Consultar historial | Todos según permisos | Lista y detalle de análisis |
| CU-09 | Revisar auditoría | Owner/Admin | Eventos trazables |
| CU-10 | Monitorear plataforma | Owner/Developer | Métricas, logs y traces |

---

## 3. Requisitos funcionales

### 3.1 Identidad y acceso

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-001 | El sistema DEBE permitir autenticación segura mediante credenciales y/o OIDC según la implementación elegida. | Alta | Usuario válido puede iniciar sesión y recibe una sesión con permisos. |
| RF-002 | El sistema DEBE soportar roles OWNER, ADMIN, ANALYST y VIEWER. | Alta | Las acciones no autorizadas son rechazadas con 403. |
| RF-003 | El sistema DEBE aislar los recursos por organización/tenant. | Alta | Un usuario no puede consultar recursos de otro tenant. |
| RF-004 | El sistema DEBE registrar eventos relevantes de autenticación y autorización. | Alta | Los eventos aparecen en el audit log con actor y timestamp. |

### 3.2 Fuentes de datos y catálogo

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-010 | El sistema DEBE permitir registrar conexiones PostgreSQL y MySQL mediante credenciales almacenadas de forma segura. | Alta | Una conexión válida se verifica con una prueba controlada. |
| RF-011 | El sistema DEBE permitir importar CSV y Excel. | Alta | El archivo válido crea un dataset consultable. |
| RF-012 | El sistema DEBE inspeccionar esquemas, tablas, columnas, tipos y metadatos mínimos. | Alta | El catálogo muestra estructura actualizada. |
| RF-013 | El sistema DEBE permitir etiquetar datasets y columnas con metadatos semánticos. | Media | El agente puede usar las anotaciones para mejorar el contexto. |
| RF-014 | El sistema DEBE detectar cambios básicos de esquema y reflejarlos en el catálogo. | Media | Un cambio de columna/tipo se marca como actualización. |

> **Nota de implementación (Fase 3b, 2026-08-15)**: RF-010 se implementó solo para
> PostgreSQL. MySQL queda diferido de forma explícita — requiere una dependencia async
> nueva y su propia infraestructura de test con una instancia real (no mocks, ver
> `.claude/rules/testing.md`) — hasta que haya necesidad concreta de soportarlo. El
> requisito en sí no cambia (sigue pidiendo ambos motores); ver el detalle de la decisión
> en `docs/architecture.md` sección 8.1 y `docs/security/threat-model.md`.

### 3.3 Agente de análisis

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-020 | El sistema DEBE aceptar preguntas en lenguaje natural relacionadas con datos disponibles. | Alta | Una pregunta válida produce una ejecución trazable o un rechazo explicado. |
| RF-021 | El agente DEBE inspeccionar el esquema antes de generar consultas cuando sea necesario. | Alta | La ejecución registra la herramienta de descubrimiento. |
| RF-022 | El agente DEBE poder formular hipótesis y ejecutar más de una consulta para investigar una pregunta compleja. | Alta | La ejecución muestra etapas y consultas utilizadas. |
| RF-023 | El agente DEBE usar herramientas explícitas para schema discovery, SQL read-only, análisis y visualización. | Alta | Cada tool call queda registrada en el trace. |
| RF-024 | El agente DEBE producir una respuesta final con resumen, evidencia y referencias a resultados internos. | Alta | La respuesta muestra de dónde se obtuvieron los hallazgos. |
| RF-025 | El sistema DEBE permitir abortar una ejecución en curso. | Media | Una ejecución activa puede cancelarse y sus workers dejan de procesarla. |

### 3.4 SQL seguro

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-030 | El sistema DEBE ejecutar consultas del agente con credenciales de solo lectura sobre fuentes externas. | Crítica | INSERT/UPDATE/DELETE/DDL no pueden ejecutarse mediante el canal del agente. |
| RF-031 | El sistema DEBE validar la sentencia SQL antes de enviarla al motor. | Crítica | Consultas no permitidas son bloqueadas y auditadas. |
| RF-032 | El sistema DEBE imponer timeout, límite de filas y límites de complejidad configurables. | Alta | Una consulta que excede límites se cancela o trunca de manera controlada. |
| RF-033 | El sistema DEBE registrar hash o referencia segura de la consulta ejecutada, actor, origen y duración. | Alta | El audit log permite reconstruir la ejecución sin exponer secretos. |

### 3.5 Análisis y visualización

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-040 | El sistema DEBE permitir agregaciones y análisis sobre resultados SQL mediante Polars cuando corresponda. | Alta | El resultado puede transformarse sin alterar la fuente. |
| RF-041 | El sistema DEBE sugerir y generar gráficos apropiados para los datos disponibles. | Media | La respuesta puede incluir al menos tabla y gráfico cuando sea útil. |
| RF-042 | El usuario DEBE poder ver los datos utilizados por el gráfico y la consulta origen. | Alta | Existe trazabilidad desde visualización hasta evidencia. |
| RF-043 | El sistema DEBE permitir exportar resultados a CSV y/o JSON en el MVP. | Media | Un resultado puede descargarse respetando permisos. |

### 3.6 Historial y auditoría

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RF-050 | El sistema DEBE almacenar el historial de análisis por usuario y tenant. | Alta | Los análisis aparecen ordenados por fecha. |
| RF-051 | El sistema DEBE permitir reabrir un análisis y revisar su contexto, estado y resultado. | Alta | La vista detalle recupera ejecución y artefactos asociados. |
| RF-052 | El sistema DEBE registrar eventos de seguridad, conexiones, consultas y ejecuciones de agentes. | Alta | Los eventos son consultables por Owner/Admin. |
| RF-053 | El sistema DEBE soportar retención configurable de logs y resultados. | Media | Los datos vencidos se archivan o eliminan según política. |

---

## 4. Requisitos no funcionales

### 4.1 Rendimiento

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RNF-001 | La API DEBE responder solicitudes CRUD comunes con p95 <= 500 ms bajo carga de referencia. | Alta | Medido con suite de carga definida en CI/entorno de staging. |
| RNF-002 | La interfaz DEBE mostrar progreso de análisis en tiempo casi real. | Alta | Actualización visible <= 1 s desde evento emitido por backend en condiciones normales. |
| RNF-003 | Las consultas del agente DEBEN tener timeout configurable, por defecto 30 s en MVP. | Alta | La consulta no puede bloquear indefinidamente un worker. |
| RNF-004 | La plataforma DEBE soportar al menos 20 análisis simultáneos en entorno de referencia del MVP. | Media | Se demuestra con prueba de concurrencia. |

### 4.2 Seguridad

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RNF-010 | Las credenciales y secretos NO DEBEN almacenarse en texto plano en tablas de negocio ni logs. | Crítica | Revisión automatizada/manual sin secretos expuestos. |
| RNF-011 | Toda comunicación cliente-servidor DEBE usar HTTPS en despliegues públicos. | Crítica | El entorno de producción redirige HTTP a HTTPS. |
| RNF-012 | El sistema DEBE aplicar RBAC y aislamiento por tenant en cada operación protegida. | Crítica | Pruebas negativas cubren acceso cruzado. |
| RNF-013 | Las consultas del agente DEBEN operar en modo read-only. | Crítica | Pruebas intentan operaciones destructivas y deben ser bloqueadas. |
| RNF-014 | El sistema DEBE aplicar límites de archivo, contenido y tamaño para importaciones. | Alta | Archivos fuera de política son rechazados. |
| RNF-015 | El sistema DEBE implementar protección contra prompt injection en contexto de datos. | Alta | Instrucciones no confiables en documentos no pueden cambiar políticas de ejecución. |

### 4.3 Disponibilidad y mantenibilidad

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RNF-020 | Los servicios DEBEN poder iniciarse reproduciblemente mediante Docker Compose. | Alta | Un desarrollador nuevo puede levantar el stack siguiendo README. |
| RNF-021 | El backend DEBE tener cobertura automatizada significativa sobre componentes críticos. | Alta | Auth, SQL validator, agent tools y API crítica tienen pruebas. |
| RNF-022 | El sistema DEBE exponer health checks de liveness y readiness. | Alta | Los endpoints reflejan estado real de dependencias críticas. |
| RNF-023 | La API NO versiona la URL (`/api/...`, sin `/v1`) mientras no exista un consumidor externo real — el contrato evoluciona en el mismo path vía commits, no vía rutas paralelas. | Media | Un cambio incompatible se documenta como decisión consciente (ver `docs/architecture.md`); versionado explícito por URL se introduce recién cuando haya un consumidor externo real que lo necesite. |

### 4.4 UX

| ID | Requisito | Prioridad | Criterio de aceptación |
|---|---|---|---|
| RNF-030 | La aplicación DEBE funcionar correctamente en desktop y tablet. | Media | No existen elementos críticos fuera de viewport en resoluciones soportadas. |
| RNF-031 | El usuario DEBE poder distinguir entre respuesta final, herramienta ejecutada, SQL y error. | Alta | La UI separa visualmente etapas de ejecución. |

---

## 5. Arquitectura de referencia

La arquitectura propuesta privilegia un backend Python unificado para AI y Data, evitando introducir microservicios prematuramente. La plataforma debe poder separarse en servicios más adelante si el tráfico o los límites de escalabilidad lo justifican.

```
Frontend   React + TypeScript + Vite
           TanStack Query + Zustand + Tailwind + Recharts
                          |
                     HTTPS / SSE
                          v
Backend    FastAPI + Pydantic v2
           Auth / RBAC / API / Agent Orchestrator
           SQL Validation / Data Services
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
   PostgreSQL           Redis             Worker
        |                 |                ARQ
        +--- pgvector      |                  |
                          +------------------+

Observability: OpenTelemetry -> Prometheus -> Grafana
Runtime: Docker Compose
CI/CD: GitHub Actions
```

> Nota: detalle de implementación de esta arquitectura (estructura de carpetas, empaquetado, división api/worker) vive en [`architecture.md`](./architecture.md).

### 5.1 Frontend

- React + TypeScript + Vite.
- TanStack Query para estado servidor y cache de API.
- Zustand solo para estado local/global que realmente lo requiera.
- Tailwind CSS para sistema visual consistente.
- Recharts para gráficos generados a partir de resultados.
- SSE para streaming de eventos del análisis y WebSocket solo donde se justifique.

### 5.2 Backend

- FastAPI con endpoints bajo `/api` (sin versión en la URL — ver RNF-023).
- Pydantic v2 para validación de contratos.
- SQLAlchemy 2.x + Alembic para persistencia de la aplicación.
- Separación clara entre ORM de la plataforma y SQL generado por IA.
- Servicios de dominio desacoplados: auth, datasets, analysis, agent, audit, observability.

### 5.3 AI / Agent Runtime

La capa de IA debe usar un runtime de agentes tipado. La selección entre PydanticAI y OpenAI Agents SDK queda como decisión de implementación, pero el sistema DEBE conservar el mismo contrato conceptual: el modelo decide cuándo usar tools; el backend decide si una tool está autorizada.

| Tool | Propósito | Entrada | Salida |
|---|---|---|---|
| inspect_schema | Descubrir estructura de datos | dataset_id | Tablas/columnas/tipos |
| execute_readonly_sql | Consultar datos | SQL + dataset | Filas, columnas, métricas |
| run_analysis | Analizar resultados | dataset tabular | Métricas y hallazgos |
| create_chart | Crear visualización | datos + intención | Especificación de gráfico |
| search_documents | Consultar contexto documental | consulta | Fragmentos relevantes |

---

## 6. Modelo de datos lógico

| Entidad | Descripción | Campos clave |
|---|---|---|
| organizations | Tenant lógico | id, name, created_at |
| users | Identidad de usuario | id, email, password_hash/oidc_id, status |
| memberships | Relación usuario-tenant | user_id, organization_id, role |
| data_sources | Conexiones externas o fuentes cargadas | id, organization_id, type, secret_ref, status |
| datasets | Catálogo de datasets | id, source_id, name, schema, metadata |
| analyses | Solicitud y estado de análisis | id, user_id, dataset_id, question, status, timestamps |
| agent_runs | Ejecuciones del agente | id, analysis_id, model, status, trace_id |
| tool_calls | Llamadas de herramientas | id, agent_run_id, tool, input_hash, duration, status |
| analysis_artifacts | Tablas, gráficos, exports | id, analysis_id, type, uri/metadata |
| audit_events | Eventos de seguridad/operación | id, organization_id, actor_id, action, target, timestamp |

### 6.1 Principios de persistencia

- Los secretos de conexiones deben referenciar un almacenamiento de secretos; no guardarlos como texto plano en business tables.
- Las preguntas, resultados y metadatos de análisis deben estar vinculados al tenant.
- Los resultados grandes deben almacenarse como artefactos o referencias, no como campos gigantes dentro de una sola fila.
- Debe existir trazabilidad entre `analysis -> agent_run -> tool_calls -> artifacts`.

---

## 7. API de referencia

| Método | Ruta | Propósito |
|---|---|---|
| POST | /api/auth/login | Autenticación |
| POST | /api/organizations | Crear organización |
| GET | /api/datasets | Listar datasets accesibles |
| POST | /api/data-sources | Registrar fuente |
| POST | /api/datasets/import | Importar CSV/Excel |
| GET | /api/datasets/{id}/schema | Consultar esquema |
| POST | /api/analyses | Crear análisis |
| GET | /api/analyses/{id} | Consultar análisis |
| POST | /api/analyses/{id}/cancel | Cancelar análisis |
| GET | /api/analyses/{id}/events | Stream SSE de eventos |
| GET | /api/analyses/{id}/artifacts | Listar artefactos |
| GET | /api/audit-events | Consultar auditoría |
| GET | /health/live | Liveness |
| GET | /health/ready | Readiness |

### 7.1 Contrato de creación de análisis

```
POST /api/analyses
{
  "dataset_id": "...",
  "question": "¿Por qué bajaron las ventas este mes?",
  "options": {
    "include_chart": true,
    "max_rows": 5000
  }
}
```

### 7.2 Estados de una ejecución

```
QUEUED -> PLANNING -> TOOL_RUNNING -> ANALYZING -> GENERATING_RESPONSE -> COMPLETED
                                                                        -> FAILED
                                                                        -> CANCELLED
                                                                        -> TIMED_OUT
```

---

## 8. Seguridad y controles de IA

La seguridad no puede depender de que el LLM "se porte bien". El principio rector es: **el modelo puede proponer; el software autoriza**. Los controles críticos deben existir fuera del prompt.

- Base de datos de solo lectura para consultas generadas por el agente.
- Parser/validator SQL que permita SELECT y expresiones explícitamente autorizadas.
- Bloqueo de DDL y DML en el camino de ejecución del agente.
- Timeout de consultas y máximo de filas retornadas.
- Rate limit por usuario y tenant.
- Separación de secretos, tokens y contexto del prompt.
- Sanitización de contenido proveniente de documentos no confiables.
- Auditoría de tool calls y decisiones críticas.
- Principio de mínimo privilegio para todos los servicios.

### 8.1 Threat model mínimo

| Amenaza | Riesgo | Control |
|---|---|---|
| Prompt injection en documento | El agente intenta ejecutar acciones no deseadas | Contexto no confiable + tools autorizadas externamente |
| SQL injection vía generación LLM | Consulta peligrosa | Parser + allowlist + DB read-only |
| Cross-tenant access | Filtración de datos | Tenant scoping obligatorio en backend y DB |
| Secret leakage | Credenciales expuestas | Secret manager/ref + redacción de logs |
| DoS por consultas pesadas | Worker/DB saturados | Timeout, límites, concurrency control |
| Carga maliciosa de archivo | Parser comprometido/consumo excesivo | Size limits, MIME validation, sandboxing |

---

## 9. Observabilidad

Cada análisis debe poder seguirse desde una solicitud HTTP hasta las llamadas al agente, consultas SQL y artefactos generados. El objetivo es poder responder en minutos preguntas como: ¿por qué fue lento?, ¿qué tool falló?, ¿qué consulta se ejecutó?, ¿cuánto costó la ejecución?

| Métrica | Ejemplo |
|---|---|
| api_request_duration_seconds | p50/p95/p99 por endpoint |
| analysis_duration_seconds | Duración total de análisis |
| agent_tool_calls_total | Cantidad por tool |
| sql_query_duration_seconds | Latencia de DB |
| analysis_failures_total | Fallos agrupados por causa |
| llm_request_duration_seconds | Latencia del proveedor de IA |
| active_workers | Workers en ejecución |
| queue_depth | Trabajos esperando |

---

## 10. Estrategia de pruebas

| Nivel | Herramienta | Objetivo |
|---|---|---|
| Unitarias | Pytest | Validar reglas de dominio, SQL validator, services y tools. |
| Integración | Pytest + Testcontainers/DB de prueba | Validar FastAPI + PostgreSQL + Redis. |
| Frontend | Vitest + React Testing Library | Validar componentes y flujos UI. |
| E2E | Playwright | Validar login, conexión de dataset, análisis y visualización. |
| Carga | k6/Locust | Validar latencias y concurrencia. |
| Seguridad | Tests negativos + scanners | Intentar superar RBAC, SQL controls y límites. |
| Evaluación IA | Dataset de preguntas esperadas | Medir exactitud SQL, faithfulness y utilidad. |

### 10.1 Evaluación específica del agente

- Exactitud de recuperación de esquema relevante.
- Validez sintáctica y semántica del SQL.
- Tasa de consultas peligrosas bloqueadas.
- Exactitud de los resultados frente a consultas de referencia.
- Trazabilidad entre afirmaciones y evidencia.
- Porcentaje de preguntas que el agente debe rechazar por falta de datos o permisos.
- Costo y latencia por análisis.

---

## 11. Entorno y despliegue

```
docker compose up -d

services:
  frontend
  api
  worker
  postgres
  redis
  prometheus
  grafana
  reverse-proxy
```

El proyecto debe incluir un entorno local reproducible y una ruta de despliegue de staging/producción. La infraestructura de producción puede comenzar en una VM o servidor administrado y posteriormente escalarse sin rediseñar el dominio.

### 11.1 CI/CD

- Instalar dependencias y validar lockfiles.
- Ejecutar linters y formatters.
- Ejecutar pruebas unitarias e integración.
- Construir frontend y backend.
- Construir imágenes Docker.
- Ejecutar escaneo de dependencias/secretos.
- Publicar artefactos y desplegar a staging.
- Ejecutar smoke tests.

---

## 12. Fuera de alcance del MVP

- Escrituras automáticas en bases de datos fuente.
- Fine-tuning de un LLM propio.
- Orquestación Kubernetes desde el primer release.
- Soporte para docenas de bases de datos exóticas.
- Marketplace de conectores.
- Facturación SaaS completa.
- Aplicaciones móviles nativas.
- Replicar capacidades de una suite BI empresarial completa.

---

## 13. Roadmap de implementación

| Fase | Entregable | Resultado |
|---|---|---|
| Fase 0 | Base del repositorio | Monorepo, Docker Compose, CI, lint, estructura. |
| Fase 1 | Auth + tenants | Usuarios, roles, aislamiento. |
| Fase 2 | Datasets | Importación CSV/Excel + PostgreSQL + catálogo. |
| Fase 3 | SQL Analyst MVP | Pregunta -> schema -> SQL -> resultado seguro. |
| Fase 4 | Agent runtime | Tools, múltiples pasos, estados, cancelación. |
| Fase 5 | Visualización | Gráficos, tablas, exportaciones. |
| Fase 6 | RAG documental | Documentos, embeddings, búsqueda híbrida y permisos. |
| Fase 7 | Observabilidad | OpenTelemetry, Prometheus, Grafana, auditoría avanzada. |
| Fase 8 | Hardening | Carga, seguridad, evaluación IA, documentación y demo. |

### 13.1 Definición de terminado (DoD)

- Código formateado y lint sin errores críticos.
- Pruebas automatizadas pasando.
- Requisito implementado y asociado a tests.
- Logs y métricas disponibles.
- No existen secretos en el repositorio.
- Docker Compose levanta el entorno desde cero.
- README actualizado con instalación, arquitectura y troubleshooting.
- Criterios de aceptación verificados manual o automáticamente.

---

## 14. Decisiones técnicas y justificación

| Decisión | Elección | Justificación |
|---|---|---|
| Backend | FastAPI + Python | Unifica AI, Data y API en un ecosistema natural; evita una frontera artificial NestJS -> Python. |
| Frontend | React + TypeScript | Amplio mercado laboral y tipado estático para una UI compleja. |
| DB principal | PostgreSQL | Relacional, JSONB, extensibilidad y posibilidad de pgvector sin añadir otra DB al inicio. |
| Data processing | Polars | Adecuado para transformaciones tabulares y eficiente para datasets mayores. |
| ORM | SQLAlchemy 2 | Maduro y flexible para persistencia de la propia plataforma. |
| Queue | Redis + ARQ | Simple y suficiente para background jobs del MVP. |
| Containers | Docker Compose | Reproducibilidad local con complejidad mínima. |
| Observability | OpenTelemetry + Prometheus + Grafana | Trazabilidad y métricas de nivel profesional. |
| Realtime | SSE primero | El flujo principal es server-to-client durante el análisis. |

> Estas son las decisiones técnicas ya fijadas por el propio SRS. Decisiones técnicas adicionales tomadas durante el desarrollo (gestor de paquetes, mecanismo concreto de autenticación, estrategia de secretos, etc.) se documentan como ADR en [`adr/`](./adr/), no en este documento.

---

## 15. Criterios de aceptación del producto

- Un usuario ANALYST puede cargar un CSV/Excel válido y verlo en el catálogo.
- El usuario puede conectar una fuente PostgreSQL/MySQL con permisos de solo lectura.
- El usuario puede preguntar en lenguaje natural por un dataset autorizado.
- El agente puede inspeccionar el esquema y generar una consulta SQL.
- Una consulta destructiva generada deliberadamente es bloqueada.
- El análisis muestra progreso en la UI y termina en COMPLETED, FAILED, CANCELLED o TIMED_OUT.
- La respuesta final incluye evidencia y artefactos, no solo texto libre.
- El usuario puede visualizar al menos un gráfico relevante generado a partir de datos.
- Un administrador puede consultar audit logs.
- Las métricas y trazas permiten localizar una ejecución concreta mediante trace_id.
- Los tests E2E cubren el flujo principal desde login hasta resultado.
- El proyecto puede ser levantado con Docker Compose siguiendo el README.

---

## 16. Requisitos de portafolio

El proyecto no solo debe funcionar; debe demostrar capacidad profesional. El repositorio DEBE contener documentación técnica que permita a un tercero entender decisiones y reproducir el sistema.

- README con problema, arquitectura, screenshots, instalación y demo.
- Diagrama de arquitectura.
- ADR (Architecture Decision Records) para decisiones importantes.
- OpenAPI documentada.
- Ejemplos de preguntas y respuestas.
- Benchmarks de latencia y procesamiento de datos.
- Threat model y controles de seguridad.
- Guía de desarrollo local.
- Guía de despliegue.
- Colección de pruebas del agente y métricas de evaluación.

---

## 17. Glosario

| Término | Definición |
|---|---|
| Agent | Componente que interpreta una tarea, decide qué herramientas usar y produce una salida. |
| Tool | Operación explícita que un agente puede invocar. |
| Dataset | Conjunto lógico de datos registrado en la plataforma. |
| Tenant | Organización aislada dentro de la plataforma. |
| RAG | Recuperación de información para aportar contexto a un modelo generativo. |
| RBAC | Control de acceso basado en roles. |
| SSE | Server-Sent Events; canal de eventos servidor -> cliente por HTTP. |
| Trace | Cadena de operaciones asociadas a una ejecución. |
| Artifact | Resultado persistente como gráfico, tabla o exportación. |

---

## 18. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El agente genera SQL incorrecto | Alto | Validación, tests de referencia, feedback y contexto de esquema. |
| Explosión de complejidad | Alto | Monolito modular primero; no microservicios prematuros. |
| Costos de LLM | Medio | Caché, límites, modelos adecuados por tarea y métricas de costo. |
| Consultas lentas | Alto | Timeout, límites, explain opcional, índices y datasets controlados. |
| Prompt injection | Alto | Separación de instrucciones, trust boundaries y autorización externa al LLM. |
| Proyecto demasiado grande | Alto | MVP estricto por fases; cada fase debe ser demostrable. |

---

## 19. Apéndice A — Estructura propuesta del repositorio (original del SRS)

> Esta es la propuesta **original** del documento fuente. La estructura efectivamente adoptada por el repositorio (con la justificación de las diferencias) está documentada en [`adr/0001-monorepo-structure.md`](./adr/0001-monorepo-structure.md) y en [`architecture.md`](./architecture.md).

```
ai-data-analyst/
├── apps/
│   ├── api/                 # FastAPI
│   ├── worker/               # ARQ workers
│   └── web/                  # React + TypeScript
├── packages/
│   └── shared-contracts/     # Contratos compartidos si aplica
├── infra/
│   ├── docker/
│   ├── postgres/
│   ├── observability/
│   └── reverse-proxy/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── evals/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── security/
│   └── api/
├── .github/workflows/
├── docker-compose.yml
└── README.md
```

### 19.1 Primer MVP recomendado

1. Levantar React + FastAPI + PostgreSQL + Redis con Docker Compose.
2. Implementar autenticación y roles básicos.
3. Crear módulo de datasets e importación CSV.
4. Implementar catálogo de esquema.
5. Implementar SQL validator y conexión read-only.
6. Crear primer agente: pregunta -> schema -> SQL -> ejecución -> respuesta.
7. Añadir SSE para streaming de eventos.
8. Añadir tabla y un gráfico.
9. Añadir historial y auditoría.
10. Agregar tests E2E y documentación del repositorio.

---

## 20. Aprobación y control de cambios

| Versión | Fecha | Descripción | Responsable |
|---|---|---|---|
| 1.0 | 2026-08-15 | SRS inicial con alcance, stack, requisitos y roadmap. | Daniel Alejandro Rosero Ortiz |

**Regla de cambio**: cualquier modificación que afecte comportamiento funcional, seguridad, datos, contratos API o arquitectura debe actualizar este SRS y los requisitos afectados antes de marcar la implementación como terminada.
