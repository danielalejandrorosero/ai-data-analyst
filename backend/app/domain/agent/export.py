import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.analysis import Analysis
from app.domain.agent.execution import SqlExecutionError, execute_readonly_query
from app.domain.datasets import service as datasets_service

# Prefijo que marca una entrada de Analysis.result_json como salida de
# run_analysis (Polars) en vez de execute_readonly_sql - ver tools.py. No es
# SQL real, no se puede re-ejecutar contra Postgres.
_POLARS_SQL_PREFIX = "[polars]"


class ExportError(Exception):
    """El indice de resultado pedido no existe en la evidencia del analysis,
    o no se pudo recuperar el resultado completo para exportar (dataset ya
    no disponible, fallo al re-ejecutar la consulta original)."""


@dataclass
class ExportPayload:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def select_result(
    results: list[dict[str, Any]] | None, *, query_index: int | None
) -> dict[str, Any]:
    """RF-043: elige que entrada de Analysis.result_json exportar. Por
    defecto la ULTIMA (la mas relevante a la respuesta final); query_index
    permite pedir una consulta anterior especifica (RF-022 puede dejar
    varias)."""
    if not results:
        raise ExportError("Este analisis todavia no tiene resultados para exportar")

    index = len(results) - 1 if query_index is None else query_index
    if index < 0 or index >= len(results):
        raise ExportError(f"query_index fuera de rango (0-{len(results) - 1})")

    return results[index]


async def build_export_payload(
    db: AsyncSession, *, analysis: Analysis, query_index: int | None
) -> ExportPayload:
    """RF-043: arma el payload completo a exportar para una entrada de
    Analysis.result_json.

    Si la entrada viene de execute_readonly_sql (su `sql` NO empieza con
    "[polars]"), la evidencia persistida esta acotada a
    tools.py::_EVIDENCE_ROW_CAP (100 filas) por diseno
    (.claude/rules/database.md) - el export completo se sirve on-demand
    re-ejecutando ese mismo SQL (ya validado y re-serializado cuando se
    corrio originalmente) contra el dataset real, hasta
    settings.agent_sql_max_rows filas.

    Si la entrada viene de run_analysis (prefijo "[polars]"), no es SQL
    real y no se puede re-ejecutar - se exporta la evidencia persistida
    tal cual, tomando su propio flag de truncamiento.
    """
    selected = select_result(analysis.result_json, query_index=query_index)
    sql = selected.get("sql") or ""

    if sql.startswith(_POLARS_SQL_PREFIX):
        truncated = bool(selected.get("truncated")) or bool(selected.get("evidence_truncated"))
        return ExportPayload(
            columns=selected["columns"], rows=selected["rows"], truncated=truncated
        )

    dataset = await datasets_service.get_dataset_by_id(db, analysis.dataset_id)
    if dataset is None:
        raise ExportError("El dataset de este analisis ya no esta disponible para exportar")

    try:
        result = await execute_readonly_query(sql, max_rows=settings.agent_sql_max_rows)
    except SqlExecutionError as exc:
        raise ExportError(
            "No se pudo recuperar el resultado completo: fallo al re-ejecutar la consulta original"
        ) from exc

    return ExportPayload(columns=result.columns, rows=result.rows, truncated=result.truncated)


def rows_to_csv(columns: list[str], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()


def rows_to_json(columns: list[str], rows: list[list[Any]]) -> str:
    return json.dumps([dict(zip(columns, row, strict=True)) for row in rows])
