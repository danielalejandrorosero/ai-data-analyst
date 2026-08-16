import hashlib
import json
import time
from typing import Any

from pydantic_ai import RunContext

from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.domain.agent.deps import AgentDeps
from app.domain.agent.execution import SqlExecutionError, execute_readonly_query
from app.domain.agent.sql_validator import SqlValidationError, validate_readonly_select


async def _record_tool_call(
    deps: AgentDeps,
    *,
    tool: str,
    input_payload: dict[str, Any],
    start: float,
    status: ToolCallStatus,
    output_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """RF-023 (cada tool call queda registrada) + RF-033 (input_hash)."""
    duration_ms = int((time.monotonic() - start) * 1000)
    input_hash = hashlib.sha256(
        json.dumps(input_payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    deps.db.add(
        ToolCall(
            agent_run_id=deps.agent_run_id,
            tool=tool,
            input_json=input_payload,
            input_hash=input_hash,
            output_summary=output_summary,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )
    )
    await deps.db.flush()


async def inspect_schema(ctx: RunContext[AgentDeps]) -> str:
    """Devuelve las columnas y tipos disponibles del dataset. Llamala
    siempre antes de escribir una consulta SQL."""
    start = time.monotonic()
    columns = [{"name": c.name, "type": c.type} for c in ctx.deps.columns]
    await _record_tool_call(
        ctx.deps,
        tool="inspect_schema",
        input_payload={},
        start=start,
        status=ToolCallStatus.SUCCESS,
        output_summary={"columns": columns},
    )
    return json.dumps({"table": ctx.deps.table_name, "columns": columns})


async def execute_readonly_sql(ctx: RunContext[AgentDeps], sql: str) -> str:
    """Ejecuta UNA consulta SELECT de solo lectura contra el dataset
    (tabla exacta que te indica inspect_schema). Si la consulta es
    rechazada, el motivo del error te dice que corregir - no reintentes
    con la misma consulta."""
    start = time.monotonic()
    try:
        validated_sql = validate_readonly_select(
            sql,
            allowed_table=ctx.deps.table_name,
            max_rows=ctx.deps.max_rows,
            max_joins=ctx.deps.max_joins,
            max_subqueries=ctx.deps.max_subqueries,
        )
    except SqlValidationError as exc:
        await _record_tool_call(
            ctx.deps,
            tool="execute_readonly_sql",
            input_payload={"sql": sql},
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=str(exc),
        )
        return f"ERROR: consulta rechazada por el validador de seguridad: {exc}"

    try:
        result = await execute_readonly_query(validated_sql, max_rows=ctx.deps.max_rows)
    except SqlExecutionError as exc:
        await _record_tool_call(
            ctx.deps,
            tool="execute_readonly_sql",
            input_payload={"sql": validated_sql},
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=str(exc),
        )
        return f"ERROR: fallo al ejecutar la consulta: {exc}"

    summary = {
        "columns": result.columns,
        "row_count": result.row_count,
        "truncated": result.truncated,
    }
    await _record_tool_call(
        ctx.deps,
        tool="execute_readonly_sql",
        input_payload={"sql": validated_sql},
        start=start,
        status=ToolCallStatus.SUCCESS,
        output_summary=summary,
    )

    # Preview acotado para no inflar el contexto del LLM ni la respuesta -
    # el resultado completo (hasta max_rows) queda en deps.last_result
    # para que el orquestador lo guarde como evidencia (RF-042).
    preview_rows = result.rows[:20]
    ctx.deps.last_result = {"sql": validated_sql, **summary, "rows": result.rows}

    return json.dumps(
        {
            "sql": validated_sql,
            "columns": result.columns,
            "rows_preview": preview_rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
    )
