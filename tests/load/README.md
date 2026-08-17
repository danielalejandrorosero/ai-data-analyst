# Load testing — RNF-001

Suite de carga para RNF-001 del SRS:

> La API DEBE responder solicitudes CRUD comunes con p95 <= 500ms bajo carga de
> referencia. Medido con suite de carga definida en CI/entorno de staging.

Esta carpeta contiene la suite y el resultado de una corrida real. **No está
integrada a CI** (decisión explícita, fuera del alcance de esta tarea) — hoy es
una herramienta para correr manualmente contra un entorno real (local Docker o
staging) y documentar el resultado.

## Qué mide, y qué NO mide

Cubre los endpoints CRUD representativos de la plataforma, con una cuenta real
autenticada:

- `POST /api/auth/login` — solo en `setup()`, una vez (ver más abajo por qué)
- `GET /health/ready` — baseline barato (chequea Postgres + Redis, sin lógica de negocio)
- `GET /api/datasets?organization_id=...` — listado, el CRUD más común
- `GET /api/datasets/{id}/schema` — detalle de un recurso
- `GET /api/analyses?organization_id=...` — listado de historial

**Deliberadamente NO mide `POST /api/analyses`** (disparar el agente de IA). Esa
ruta encola un job que llama a un LLM externo (Moonshot/Kimi vía PydanticAI) con
latencia y costo variables ajenos a la plataforma — medir eso sería medir al
proveedor del LLM, no "nuestra" API. Si en el futuro se quiere medir el
throughput de encolado en sí (la respuesta 202 inmediata, sin esperar a que el
worker termine), es una suite aparte con su propio criterio.

## Herramienta: k6

Se usó [k6](https://k6.io/) (instalado vía `winget install -e --id GrafanaLabs.k6`,
v2.2.0) en vez de Locust porque estaba disponible por winget sin fricción de
permisos. Si no hay forma de instalar k6 en el entorno donde se corra esto,
`locustfile.py` no existe todavía en este repo — habría que escribirlo
replicando la misma lógica (login en `on_start`, resto de los endpoints en el
loop de tareas).

## Autenticación y rate limiting

`POST /api/auth/login` tiene rate limit de **5/minuto por IP**
(`backend/app/core/rate_limit.py`, `settings.rate_limit_auth`). La suite hace
login **una sola vez**, dentro de `setup()` de k6 (que corre una vez sin
importar VUs/iteraciones/duración), y reutiliza el mismo JWT para todas las
iteraciones de todos los VUs — el mismo patrón que una SPA real con sesión
persistente. Los demás endpoints cubiertos acá no tienen rate limit (o uno
mucho más alto, y de todas formas no aplica a GETs).

Cuenta usada: `fase2test@example.com` (cuenta de prueba ya existente, no se
registró una cuenta nueva — no interfiere con los datasets cargados porque la
suite solo hace lecturas). Configurable vía env vars:

```
LOAD_TEST_EMAIL=otra@cuenta.com
LOAD_TEST_PASSWORD=otrapassword
BASE_URL=http://localhost:8000
```

## Carga de referencia (definición explícita)

El SRS no fija un número para este RNF puntual (a diferencia de RNF-004, que sí
fija "20 análisis de agente simultáneos" — un requisito distinto, sobre el
agente, no sobre CRUD). Para RNF-001 se define acá, de forma explícita y
razonable:

**20 usuarios virtuales concurrentes, sostenidos 60 segundos**, con rampas de
10s arriba y 10s abajo (perfil `ramping-vus` de k6) para no medir un escalón
artificial. Cada VU hace un `sleep(1)` de think-time entre iteraciones. Es un
perfil de carga moderada/smoke test para una API CRUD, no una prueba de stress
ni de búsqueda de límite de capacidad.

## Cómo correrlo

```bash
k6 run tests/load/k6-crud.js
```

Para exportar el resumen a JSON (lo que se usó para `last_run_results.md`):

```bash
k6 run --summary-export tests/load/last_run_summary.json tests/load/k6-crud.js
```

Contra otro entorno/cuenta:

```bash
BASE_URL=https://staging.example.com LOAD_TEST_EMAIL=carga@example.com LOAD_TEST_PASSWORD=... k6 run tests/load/k6-crud.js
```

## Resultado de la última corrida real

Ver `tests/load/last_run_results.md`. Resumen: **el RNF-001 NO se cumple hoy
para todos los endpoints** bajo esta carga de referencia — `GET /health/ready`
superó 500ms de p95. El resto de los endpoints cumplió, pero con margen
ajustado (`datasets_list` p95=465ms, cerca del límite). Detalle completo,
números sin redondear favorablemente, y una hipótesis de causa raíz (un solo
worker de uvicorn) en ese archivo.
