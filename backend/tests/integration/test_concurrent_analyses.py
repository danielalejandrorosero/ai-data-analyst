"""RNF-004: "La plataforma DEBE soportar al menos 20 analisis simultaneos en
entorno de referencia del MVP. Se demuestra con prueba de concurrencia."

`TestOrchestratorConcurrentToolCalls` en test_agent_orchestrator.py prueba otra
cosa: una condicion de carrera del PRESUPUESTO de tool calls DENTRO de un unico
analisis (20 tool calls en el mismo turno de UN analisis). Este archivo prueba
lo que el RNF realmente pide: 20 analisis SIMULTANEOS del sistema completo.

## Por que esto NO usa el fixture `client` (ASGITransport) del resto de la suite

`client` corre la app FastAPI in-process, sin un worker ARQ real de fondo -
sirve para probar el contrato HTTP, pero un job encolado ahi nunca lo procesa
nadie (no hay worker escuchando esa cola de Redis "de prueba" en background
durante el test). Probar concurrencia de WORKERS reales requiere que el job se
procese de verdad, en paralelo, fuera del proceso de pytest.

## Opcion elegida: A (sistema real end-to-end), no B (TestModel simulado)

Se opto por golpear el sistema real ya corriendo en Docker (API en
localhost:8000, worker ARQ real, Postgres real) con requests HTTP concurrentes,
en vez de invocar `run_analysis()` 20 veces con un modelo simulado
(TestModel/FunctionModel) dentro del proceso de pytest. La opcion B habria
probado la capa de orquestacion en aislamiento (utilidad real, pero no lo que
pide el RNF); la opcion A prueba "la plataforma" tal como el usuario final la
usa: API real -> cola real -> worker ARQ real -> Postgres real. El costo es
que depende de un LLM real (Kimi/Moonshot, ya configurado en el worker) y de
que los servicios de docker-compose esten arriba.

## Como correrlo

Requiere `docker compose up` (api, worker, postgres, redis) y la cuenta de
prueba fase2test@example.com / correcthorsebattery con al menos un dataset
importado en su organizacion. NO corre en CI ni en `pytest` por defecto (no es
hermetico: usa la base de datos real de desarrollo vista por
localhost:8000, no la `ai_data_analyst_test` aislada del resto de la suite, y
tarda varios minutos con costo real de LLM). Se activa explicitamente:

    RUN_REAL_SERVICES_TESTS=1 uv run --package backend pytest \
        backend/tests/integration/test_concurrent_analyses.py -s

No modifica ni borra datos existentes de esa organizacion - solo agrega 20
analisis nuevos sobre un dataset ya importado.
"""

import asyncio
import os
import time

import httpx
import pytest

BASE_URL = os.environ.get("CONCURRENCY_TEST_BASE_URL", "http://localhost:8000/api")
TEST_EMAIL = "fase2test@example.com"
TEST_PASSWORD = "correcthorsebattery"
PREFERRED_DATASET_NAME = "Mini Test"
N_ANALYSES = 20
POLL_INTERVAL_SECONDS = 2.0
# El orchestrator impone un timeout interno de agent_sql_timeout_seconds * 4
# (docs/architecture.md, backend/app/domain/agent/orchestrator.py) - con el
# valor real del worker (30s) son 120s por analysis. Se deja margen extra
# arriba de eso para no confundir "todavia no termino" con "esta colgado".
PER_ANALYSIS_TIMEOUT_SECONDS = 200

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_SERVICES_TESTS") != "1",
    reason=(
        "Depende de API+worker ARQ+Postgres reales en Docker (docker compose "
        "up) y de un LLM real - no corre en CI ni en `pytest` por defecto. "
        "Activar con RUN_REAL_SERVICES_TESTS=1."
    ),
)


async def _login(client: httpx.AsyncClient) -> tuple[str, str]:
    response = await client.post(
        "/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    response.raise_for_status()
    body = response.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


async def _find_dataset_id(client: httpx.AsyncClient, token: str, org_id: str) -> str:
    response = await client.get(
        "/datasets",
        params={"organization_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    datasets = response.json()
    assert datasets, (
        "La organizacion de fase2test@example.com no tiene ningun dataset "
        "importado - hace falta al menos uno para correr este test."
    )
    for dataset in datasets:
        if dataset["name"] == PREFERRED_DATASET_NAME:
            return dataset["id"]
    # Fallback: el dataset mas chico disponible, para no atarse a que el seed
    # exacto "Mini Test" siga existiendo con ese nombre.
    return min(datasets, key=lambda d: d["row_count"])["id"]


async def _create_analysis(
    client: httpx.AsyncClient, token: str, dataset_id: str, index: int
) -> str:
    question = f"Cuantas filas tiene este dataset en total? (prueba de concurrencia #{index})"
    response = await client.post(
        "/analyses",
        json={"dataset_id": dataset_id, "question": question},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()["id"]


async def _poll_until_terminal(
    client: httpx.AsyncClient, token: str, analysis_id: str, t0: float
) -> dict:
    deadline = time.monotonic() + PER_ANALYSIS_TIMEOUT_SECONDS
    last_status = None
    while True:
        response = await client.get(
            f"/analyses/{analysis_id}", headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        body = response.json()
        last_status = body["status"]
        if last_status in TERMINAL_STATUSES:
            return {
                "id": analysis_id,
                "status": last_status,
                "error": body.get("error"),
                "elapsed_s": time.monotonic() - t0,
            }
        if time.monotonic() > deadline:
            return {
                "id": analysis_id,
                "status": "POLL_TIMEOUT",
                "error": f"seguia en {last_status} tras {PER_ANALYSIS_TIMEOUT_SECONDS}s de polling",
                "elapsed_s": time.monotonic() - t0,
            }
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


class TestTwentyConcurrentAnalyses:
    async def test_twenty_analyses_run_concurrently_against_real_system(self):
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            token, org_id = await _login(client)
            dataset_id = await _find_dataset_id(client, token, org_id)

            t0 = time.monotonic()
            analysis_ids = await asyncio.gather(
                *[_create_analysis(client, token, dataset_id, i) for i in range(N_ANALYSES)]
            )
            t_launch_done = time.monotonic() - t0
            print(f"\n[concurrency] {N_ANALYSES} POST /analyses lanzados en {t_launch_done:.2f}s")

            results = await asyncio.gather(
                *[_poll_until_terminal(client, token, aid, t0) for aid in analysis_ids]
            )

        total_wall_time_s = max(r["elapsed_s"] for r in results)
        by_status: dict[str, list[str]] = {}
        for r in results:
            by_status.setdefault(r["status"], []).append(r["id"])
        durations = sorted(round(r["elapsed_s"], 1) for r in results)

        print(
            f"[concurrency] tiempo total desde el primer POST hasta que "
            f"termino el ultimo: {total_wall_time_s:.2f}s"
        )
        for status, ids in sorted(by_status.items()):
            print(f"[concurrency] {status}: {len(ids)}")
        print(f"[concurrency] duraciones individuales (s), ordenadas: {durations}")
        for r in results:
            if r["status"] not in ("COMPLETED",):
                print(f"[concurrency] {r['id']} status={r['status']} error={r['error']!r}")

        timed_out_polling = by_status.get("POLL_TIMEOUT", [])
        assert not timed_out_polling, (
            f"{len(timed_out_polling)} analisis no llegaron a un estado terminal "
            f"dentro de {PER_ANALYSIS_TIMEOUT_SECONDS}s de polling: {timed_out_polling}"
        )
        assert len(results) == N_ANALYSES
