# Resultado real — corrida del 2026-08-16 (post-fix)

Entorno: backend FastAPI real corriendo en Docker Compose local
(`ai-data-analyst-api-1`), Postgres y Redis reales en contenedores del mismo
compose, contra `http://localhost:8000`. `uvicorn` con `--workers 2`
(`infrastructure/docker/backend.Dockerfile` línea 21) — fix aplicado tras la
corrida anterior, que documentaba `GET /health/ready` incumpliendo el RNF-001
con un solo proceso/event loop.

Herramienta: k6 v2.2.0 (`k6 run --summary-export tests/load/last_run_summary.json tests/load/k6-crud.js`).

Carga: 20 VUs, ramp-up 10s, sostenido 60s, ramp-down 10s (`tests/load/k6-crud.js`,
escenario `crud_reference_load`). Cuenta: `fase2test@example.com`, misma
organización y dataset de referencia que la corrida anterior.

Duración total de la corrida: 1m21s. Iteraciones completas: 1369. Requests
HTTP totales: 5478. **0 errores** (`http_req_failed` = 0.00%, 5478/5478
exitosos, todos los `check` de status 200 pasaron: 5476/5476).

## Resultado por endpoint (ms), tal como lo reportó k6 — sin redondear a favor

| Endpoint | p50 (med) | p90 | p95 | max | avg | Cumple p95<=500ms |
|---|---|---|---|---|---|---|
| `GET /health/ready` | 4.44 | 6.48 | **8.27** | 185.28 | 5.76 | **Sí** |
| `GET /api/datasets` (list) | 6.57 | 8.31 | 9.43 | 44.60 | 6.98 | Sí |
| `GET /api/datasets/{id}/schema` | 6.01 | 7.53 | 8.99 | 20.91 | 6.36 | Sí |
| `GET /api/analyses` (list) | 9.34 | 11.68 | 13.59 | 188.78 | 10.34 | Sí |
| Global (`http_req_duration`, todos los endpoints mezclados) | 6.43 | 10.07 | 11.25 | 188.78 | 7.38 | Sí |

`POST /api/auth/login` no está en la tabla: corre una única vez en `setup()`,
fuera de la ventana de carga sostenida — no es representativo medirlo con n=1.

## Veredicto sobre RNF-001

**Se cumple para los cuatro endpoints medidos**, con margen amplio (el p95 más
alto, `analyses_list`, queda en 13.59ms — muy por debajo del límite de
500ms). k6 marcó los seis thresholds configurados (los cuatro por endpoint +
`http_req_duration` global + `http_req_failed`) como `true`, exit code 0.

Comparado contra la corrida anterior (documentada como fallo, ver historial
git de este archivo): `health_ready` p95 bajó de 579.44ms a 8.27ms —
mejora de ~70x, no marginal. El resto de los endpoints también mejoró en el
mismo orden de magnitud.

## Causa raíz confirmada

La hipótesis de la corrida anterior (un único proceso/event loop de uvicorn
serializando efectivamente la carga concurrente) se confirma con este
resultado: el único cambio entre ambas corridas fue agregar `--workers 2` al
`CMD` de `infrastructure/docker/backend.Dockerfile`, y eso solo bastó para
eliminar por completo la cola larga de latencia (antes: máximos de >1.1s
simultáneos en los cuatro endpoints, indicio de contención compartida; ahora:
máximos de 185-189ms, todavía visibles pero muy por debajo del límite del
RNF).

## Cómo reproducir

```bash
k6 run --summary-export tests/load/last_run_summary.json tests/load/k6-crud.js
```

El JSON crudo de esta corrida queda en `tests/load/last_run_summary.json`
(token de auth redactado a mano antes de dejarlo en el repo).
