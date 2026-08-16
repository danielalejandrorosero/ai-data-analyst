import csv
import io
import json
from typing import Any


class ExportError(Exception):
    """El indice de resultado pedido no existe en la evidencia del analysis."""


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


def rows_to_csv(columns: list[str], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()


def rows_to_json(columns: list[str], rows: list[list[Any]]) -> str:
    return json.dumps([dict(zip(columns, row, strict=True)) for row in rows])
