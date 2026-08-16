import hashlib
import json
import time
from typing import Any

from pydantic_ai import RunContext

from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.domain.agent.deps import AgentDeps
from app.domain.agent.events import publish_event
from app.domain.agent.execution import SqlExecutionError, execute_readonly_query
from app.domain.agent.sql_validator import SqlValidationError, validate_readonly_select

# Tope de filas guardadas como evidencia por consulta en Analysis.result_json
# (no el limite de filas que la consulta puede LEER, eso es max_rows) - ver
# comentario en execute_readonly_sql.
_EVIDENCE_ROW_CAP = 100


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
    await publish_event(
        ctx.deps.analysis_id, {"type": "tool_call", "tool": "inspect_schema", "status": "SUCCESS"}
    )
    return json.dumps({"table": ctx.deps.table_name, "columns": columns})


async def execute_readonly_sql(ctx: RunContext[AgentDeps], sql: str) -> str:
    """Ejecuta UNA consulta SELECT de solo lectura contra el dataset (tabla
    exacta que te indica inspect_schema). Para preguntas complejas podes
    llamar esta herramienta mas de una vez (hasta el limite configurado) -
    cada consulta exitosa queda como evidencia separada. Si una consulta es
    rechazada, el motivo del error te dice que corregir - no reintentes
    con la misma consulta."""
    start = time.monotonic()

    # Chequeo + reserva SINCRONICOS, sin ningun await de por medio - es lo
    # que hace esto atomico frente a tool calls concurrentes del mismo
    # turno (pydantic-ai puede ejecutar varias execute_readonly_sql en
    # paralelo por default). Si el tope se chequeara contra
    # len(ctx.deps.results) -que solo crece DESPUES del round-trip a
    # Postgres- todas las llamadas concurrentes verian el mismo valor
    # viejo y se saltarian el limite. query_count se incrementa aca mismo,
    # antes de validar o ejecutar nada, para que ninguna otra tool call
    # concurrente pueda colarse entre el chequeo y la reserva.
    if ctx.deps.query_count >= ctx.deps.max_queries_per_run:
        await _record_tool_call(
            ctx.deps,
            tool="execute_readonly_sql",
            input_payload={"sql": sql},
            start=start,
            status=ToolCallStatus.ERROR,
            error_message="Limite de consultas por analisis alcanzado",
        )
        return (
            f"ERROR: ya alcanzaste el limite de {ctx.deps.max_queries_per_run} consultas "
            "para este analisis - respondé con lo que ya obtuviste."
        )
    ctx.deps.query_count += 1

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
        await publish_event(
            ctx.deps.analysis_id,
            {"type": "tool_call", "tool": "execute_readonly_sql", "status": "ERROR"},
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
        await publish_event(
            ctx.deps.analysis_id,
            {"type": "tool_call", "tool": "execute_readonly_sql", "status": "ERROR"},
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
    await publish_event(
        ctx.deps.analysis_id,
        {"type": "tool_call", "tool": "execute_readonly_sql", "status": "SUCCESS"},
    )

    # Preview acotado para no inflar el contexto del LLM ni la respuesta.
    preview_rows = result.rows[:20]

    # La evidencia que se persiste en Analysis.result_json (RF-022/RF-042)
    # tambien se acota - guardar las filas completas (hasta max_rows=5000)
    # POR CADA consulta exitosa (hasta max_queries_per_run=5) podria dejar
    # ~25000 filas en una unica columna JSONB, justo lo que
    # .claude/rules/database.md prohibe explicitamente ("nunca como
    # columna gigante dentro de una fila"). El export/artefacto completo
    # es RF-042/analysis_artifacts (Fase 5, todavia no implementado) - acá
    # solo guardamos una muestra suficiente para sustentar la respuesta,
    # no el dataset entero.
    evidence_rows = result.rows[:_EVIDENCE_ROW_CAP]
    ctx.deps.results.append(
        {
            "sql": validated_sql,
            **summary,
            "rows": evidence_rows,
            "evidence_truncated": len(result.rows) > _EVIDENCE_ROW_CAP,
        }
    )

    return json.dumps(
        {
            "sql": validated_sql,
            "columns": result.columns,
            "rows_preview": preview_rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
    )
