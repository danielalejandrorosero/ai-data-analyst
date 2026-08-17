"""Runner de evaluacion del agente (SRS seccion 10.1 / seccion 16).

Script standalone (NO es un test de pytest) que corre `reference_questions.json`
contra el sistema REAL (API FastAPI real -> worker ARQ real -> agente PydanticAI
real -> Postgres real), mide exactitud/faithfulness/tasa de rechazo/latencia/tool
calls, y deja un resumen en consola + `last_run_results.json`.

Uso:
    cd backend
    uv run python tests/evals/run_eval.py

Variables de entorno opcionales:
    EVAL_BASE_URL   (default: http://localhost:8000)
    EVAL_EMAIL      (default: fase2test@example.com)
    EVAL_PASSWORD   (default: correcthorsebattery)
    EVAL_TIMEOUT_S  (default: 60)     -- timeout de polling por pregunta
    EVAL_POLL_S     (default: 2)      -- intervalo de polling

Nota sobre datasets: las preguntas de referencia apuntan a copias
(*_eval, ver dataset_lookup_name en reference_questions.json) de los
datasets reales (diamantes, titanic, pinguinos, backlog), subidas via
el endpoint de import ya autorizado bajo la propia organizacion de la
cuenta de eval - no la organizacion original de esos datasets, a la que
esta cuenta no tiene membership. Mismos datos (fila por fila), tenant
distinto.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:8000")
EMAIL = os.environ.get("EVAL_EMAIL", "fase2test@example.com")
PASSWORD = os.environ.get("EVAL_PASSWORD", "correcthorsebattery")
POLL_TIMEOUT_S = float(os.environ.get("EVAL_TIMEOUT_S", "120"))
POLL_INTERVAL_S = float(os.environ.get("EVAL_POLL_S", "2"))

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}

# Nota: la primera corrida real (2026-08-16) mostro que el agente rechaza
# correctamente en TODOS los casos de categoria "rejection", pero con
# frases mas variadas que la lista original de este runner ("no contiene",
# "no incluye", "no es posible determinar/obtener", etc.) - la lista de
# abajo se amplio en base a las respuestas reales observadas, no se
# adivino de antemano.
REJECTION_PHRASES = [
    "no tengo esa informacion",
    "no tengo esa información",
    "no está disponible",
    "no esta disponible",
    "no puedo responder",
    "no cuento con",
    "no dispongo de",
    "no existe esa columna",
    "no existe esa informacion",
    "no existe esa información",
    "no hay informacion",
    "no hay información",
    "no es posible responder",
    "no es posible determinar",
    "no es posible obtener",
    "no es posible calcular",
    "sin datos suficientes",
    "no se encuentra disponible",
    "no forma parte del dataset",
    "no está presente en el dataset",
    "no esta presente en el dataset",
    "no contiene",
    "no incluye",
    "no hay campos de",
    "no hay campo de",
    "not available",
    "don't have",
    "do not have",
    "cannot answer",
    "can't answer",
    "no information",
]

THIS_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = THIS_DIR / "reference_questions.json"
RESULTS_PATH = THIS_DIR / "last_run_results.json"


@dataclass
class QuestionResult:
    id: str
    dataset_name: str
    category: str
    question: str
    status: str = "UNKNOWN"
    answer: str | None = None
    error: str | None = None
    latency_s: float | None = None
    tool_call_count: int = 0
    generated_sql: list[str] = field(default_factory=list)
    accuracy_pass: bool | None = None  # None = no aplica (rejection sin match de accuracy)
    rejection_pass: bool | None = None  # solo para category == "rejection"
    sql_pattern_match_ratio: float | None = None
    analysis_id: str | None = None


def _login(client: httpx.Client) -> tuple[str, str]:
    resp = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    org_id = body["user"]["memberships"][0]["organization_id"]
    return token, org_id


def _load_dataset_map(client: httpx.Client, token: str, org_id: str) -> dict[str, str]:
    resp = client.get(
        "/api/datasets",
        params={"organization_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return {ds["name"]: ds["id"] for ds in resp.json()}


def _normalize_es_numbers(text: str) -> str:
    """El agente a veces formatea numeros en estilo es-ES/es-CO (coma
    decimal, punto de miles: "4.358,76") y a veces en estilo plano
    (punto decimal: "4358.76") - inconsistente pero ambos matematicamente
    correctos. Sin esto, un chequeo de substring literal falla contra
    respuestas correctas solo por el formato. Convierte todo a notacion
    plana con punto decimal antes de buscar los valores esperados."""
    # "4.358,76" o "38,79" -> "4358.76" / "38.79" (coma decimal, con o sin
    # separador de miles por punto delante).
    text = re.sub(
        r"(\d{1,3}(?:\.\d{3})*),(\d+)",
        lambda m: m.group(1).replace(".", "") + "." + m.group(2),
        text,
    )
    # Miles con punto y sin parte decimal, ej. "5.076" -> "5076".
    text = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", text)
    return text


def _substring_hits(haystack: str, needles: list[str]) -> tuple[int, list[str]]:
    haystack_low = haystack.lower()
    haystack_norm = _normalize_es_numbers(haystack).lower()
    hits = [n for n in needles if n.lower() in haystack_low or n.lower() in haystack_norm]
    return len(hits), hits


def _looks_like_rejection(answer: str) -> bool:
    answer_low = answer.lower()
    return any(phrase in answer_low for phrase in REJECTION_PHRASES)


def _sql_pattern_match_ratio(pattern: str, actual_sql: str) -> float:
    """Chequeo laxo (no regex estricta): extrae las 'palabras clave'
    alfanumericas del patron esperado (ignora conectores SQL genericos como
    SELECT/FROM/WHERE que casi cualquier query real va a tener) y mide que
    fraccion aparece en el SQL generado, case-insensitive. Sirve solo para
    reportar, no para pasar/fallar duro (ver instrucciones de la Parte 2)."""
    if pattern.startswith("N/A"):
        return 1.0 if not actual_sql.strip() else 0.0
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", pattern)
    ignore = {
        "SELECT", "FROM", "WHERE", "AND", "OR", "AS", "ON", "BY", "IN", "NOT",
    }
    keywords = [t for t in tokens if t.upper() not in ignore]
    if not keywords:
        return 1.0
    actual_low = actual_sql.lower()
    hits = sum(1 for kw in keywords if kw.lower() in actual_low)
    return hits / len(keywords)


def _run_one_question(
    client: httpx.Client, token: str, dataset_id: str, q: dict[str, Any]
) -> QuestionResult:
    result = QuestionResult(
        id=q["id"],
        dataset_name=q["dataset_name"],
        category=q["category"],
        question=q["question"],
    )

    create_resp = client.post(
        "/api/analyses",
        json={"dataset_id": dataset_id, "question": q["question"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    if create_resp.status_code != 202:
        result.status = "CREATE_FAILED"
        result.error = f"HTTP {create_resp.status_code}: {create_resp.text[:300]}"
        return result

    analysis_id = create_resp.json()["id"]
    result.analysis_id = analysis_id

    start = time.monotonic()
    deadline = start + POLL_TIMEOUT_S
    final_body: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        get_resp = client.get(
            f"/api/analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        get_resp.raise_for_status()
        body = get_resp.json()
        if body["status"] in TERMINAL_STATUSES:
            final_body = body
            break
        time.sleep(POLL_INTERVAL_S)
    result.latency_s = round(time.monotonic() - start, 2)

    if final_body is None:
        result.status = "TIMEOUT"
        result.error = f"No llego a estado terminal en {POLL_TIMEOUT_S}s"
        return result

    result.status = final_body["status"]
    result.answer = final_body.get("answer")
    result.error = final_body.get("error")
    result.tool_call_count = len(final_body.get("tool_calls") or [])
    result.generated_sql = [
        entry.get("sql", "") for entry in (final_body.get("result") or []) if entry.get("sql")
    ]

    answer_text = result.answer or ""
    joined_sql = " | ".join(result.generated_sql)
    result.sql_pattern_match_ratio = round(
        _sql_pattern_match_ratio(q["expected_sql_pattern"], joined_sql), 2
    )

    if q["category"] == "rejection":
        result.rejection_pass = _looks_like_rejection(answer_text)
        # Para rejection, "accuracy" = rechazo correcto (no inventar un dato).
        result.accuracy_pass = result.rejection_pass
    else:
        hit_count, _hits = _substring_hits(answer_text, q["expected_answer_contains"])
        result.accuracy_pass = hit_count > 0

    return result


def _print_table(results: list[QuestionResult]) -> None:
    header = f"{'id':<16} {'categoria':<12} {'status':<10} {'acc':<5} {'rechazo':<8} {'lat(s)':<7} {'tools':<6}"
    print(header)
    print("-" * len(header))
    for r in results:
        acc = "PASS" if r.accuracy_pass else ("FAIL" if r.accuracy_pass is not None else "-")
        rej = (
            "-"
            if r.rejection_pass is None
            else ("PASS" if r.rejection_pass else "FAIL")
        )
        lat = f"{r.latency_s:.1f}" if r.latency_s is not None else "-"
        print(
            f"{r.id:<16} {r.category:<12} {r.status:<10} {acc:<5} {rej:<8} {lat:<7} {r.tool_call_count:<6}"
        )


def _print_summary(results: list[QuestionResult]) -> None:
    total = len(results)
    scored = [r for r in results if r.accuracy_pass is not None]
    passed = [r for r in scored if r.accuracy_pass]
    print()
    print("=== Resumen agregado ===")
    print(f"Total preguntas: {total}")
    if scored:
        print(f"Exactitud total: {len(passed)}/{len(scored)} = {100 * len(passed) / len(scored):.1f}%")
    else:
        print("Exactitud total: N/A (0 preguntas evaluables)")

    categories = sorted({r.category for r in results})
    for cat in categories:
        cat_results = [r for r in scored if r.category == cat]
        if not cat_results:
            continue
        cat_pass = sum(1 for r in cat_results if r.accuracy_pass)
        print(
            f"  - {cat:<12}: {cat_pass}/{len(cat_results)} = {100 * cat_pass / len(cat_results):.1f}%"
        )

    rejection_results = [r for r in results if r.category == "rejection"]
    if rejection_results:
        rej_pass = sum(1 for r in rejection_results if r.rejection_pass)
        print(
            f"Tasa de rechazo correcto (categoria rejection): {rej_pass}/{len(rejection_results)} "
            f"= {100 * rej_pass / len(rejection_results):.1f}%"
        )

    latencies = [r.latency_s for r in results if r.latency_s is not None]
    if latencies:
        avg_lat = statistics.mean(latencies)
        p95_lat = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 2 else latencies[0]
        print(f"Latencia promedio: {avg_lat:.2f}s | p95: {p95_lat:.2f}s")

    tool_calls = [r.tool_call_count for r in results]
    if tool_calls:
        print(f"Tool calls promedio por pregunta: {statistics.mean(tool_calls):.2f}")

    errored = [r for r in results if r.status not in {"COMPLETED"}]
    if errored:
        print()
        print("Preguntas que NO terminaron en COMPLETED:")
        for r in errored:
            print(f"  - {r.id} ({r.status}): {r.error}")


def main() -> int:
    if not QUESTIONS_PATH.exists():
        print(f"No se encontro {QUESTIONS_PATH}", file=sys.stderr)
        return 1

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        print(f"Login como {EMAIL} contra {BASE_URL} ...")
        token, org_id = _login(client)
        print(f"OK. organization_id={org_id}")

        dataset_map = _load_dataset_map(client, token, org_id)

        results: list[QuestionResult] = []
        for i, q in enumerate(questions, start=1):
            lookup_name = q.get("dataset_lookup_name", q["dataset_name"])
            dataset_id = dataset_map.get(lookup_name)
            print(f"[{i}/{len(questions)}] {q['id']} ({q['category']}) ...", end=" ", flush=True)

            if dataset_id is None:
                r = QuestionResult(
                    id=q["id"],
                    dataset_name=q["dataset_name"],
                    category=q["category"],
                    question=q["question"],
                    status="DATASET_NOT_FOUND",
                    error=f"No se encontro dataset '{lookup_name}' en organization_id={org_id}",
                )
                results.append(r)
                print("DATASET_NOT_FOUND")
                continue

            r = _run_one_question(client, token, dataset_id, q)
            results.append(r)
            print(f"{r.status} en {r.latency_s}s (acc={r.accuracy_pass})")

    print()
    _print_table(results)
    _print_summary(results)

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "base_url": BASE_URL,
                "email": EMAIL,
                "results": [
                    {
                        "id": r.id,
                        "dataset_name": r.dataset_name,
                        "category": r.category,
                        "question": r.question,
                        "status": r.status,
                        "answer": r.answer,
                        "error": r.error,
                        "latency_s": r.latency_s,
                        "tool_call_count": r.tool_call_count,
                        "generated_sql": r.generated_sql,
                        "accuracy_pass": r.accuracy_pass,
                        "rejection_pass": r.rejection_pass,
                        "sql_pattern_match_ratio": r.sql_pattern_match_ratio,
                        "analysis_id": r.analysis_id,
                    }
                    for r in results
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nResultados completos escritos en {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
