import hashlib
import json
import time
from typing import Any

import polars as pl
from pydantic_ai import RunContext

from app.db.models.analysis_artifact import AnalysisArtifact, ArtifactType
from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.domain.agent.deps import AgentDeps
from app.domain.agent.events import publish_event
from app.domain.agent.execution import SqlExecutionError, execute_readonly_query
from app.domain.agent.sql_validator import SqlValidationError, validate_readonly_select

# Tope de filas guardadas como evidencia por consulta en Analysis.result_json
# (no el limite de filas que la consulta puede LEER, eso es max_rows) - ver
# comentario en execute_readonly_sql.
_EVIDENCE_ROW_CAP = 100

# RF-040: funciones de agregacion permitidas para run_analysis - allowlist
# explicita (nunca eval/exec de codigo arbitrario del modelo). Coinciden 1:1
# con metodos reales de polars.col(...), asi que se resuelven con getattr()
# de forma segura porque la entrada ya paso por este chequeo antes.
_AGG_FUNCS = {"sum", "mean", "min", "max", "count"}

# RF-041: tipos de grafico que create_chart puede especificar - el frontend
# (Recharts) decide como renderizar cada uno, esto solo fija el contrato.
_CHART_TYPES = {"bar", "line", "pie", "scatter"}


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
    # columna gigante dentro de una fila"). El export completo (RF-043) se
    # sirve on-demand desde la fuente, no desde esta evidencia acotada -
    # acá solo guardamos una muestra suficiente para sustentar la
    # respuesta y alimentar create_chart, no el dataset entero.
    evidence_rows = result.rows[:_EVIDENCE_ROW_CAP]
    ctx.deps.results.append(
        {
            "sql": validated_sql,
            **summary,
            "rows": evidence_rows,
            "evidence_truncated": len(result.rows) > _EVIDENCE_ROW_CAP,
        }
    )
    # Buffer de trabajo COMPLETO (hasta max_rows, no acotado a
    # _EVIDENCE_ROW_CAP) - run_analysis/create_chart leen de aca, nunca de
    # `results` (que es solo para persistencia). Ver deps.py.
    ctx.deps.last_full_result = {
        "sql": validated_sql,
        "columns": result.columns,
        "rows": result.rows,
        "truncated": result.truncated,
    }

    return json.dumps(
        {
            "sql": validated_sql,
            "columns": result.columns,
            "rows_preview": preview_rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
    )


async def run_analysis(
    ctx: RunContext[AgentDeps],
    group_by: list[str],
    agg: dict[str, str],
    sort_by: str | None = None,
    descending: bool = False,
    limit: int | None = None,
) -> str:
    """RF-040: post-procesa el resultado de la ULTIMA consulta exitosa con
    Polars (pivots/rankings/derivados que una unica consulta SQL sobre una
    tabla no resuelve comodo) - no ejecuta SQL nuevo, no toca la base de
    datos. Llama primero a execute_readonly_sql. group_by: columnas para
    agrupar (lista vacia = agregar sobre todo el resultado). agg: mapa
    columna -> funcion, funcion en sum/mean/min/max/count. Las columnas de
    salida se llaman "{columna}_{funcion}" (ej. units_sum).

    Nota: las columnas Date/DateTime del dataset original ya llegan aca
    como strings ISO-8601 (execution.py::_json_safe las serializa antes),
    no como tipo fecha - Polars las infiere como Utf8. min/max siguen
    dando el resultado correcto (el orden lexicografico ISO-8601 coincide
    con el cronologico), pero sum/mean sobre una columna de fecha no tiene
    sentido semantico y el allowlist _AGG_FUNCS no lo distingue - si
    ocurre, Polars lo rechaza y cae en el except de abajo (ERROR
    controlado al modelo, no un fallo silencioso ni un analysis roto).
    """
    start = time.monotonic()

    # Reserva sincronica, mismo motivo que en execute_readonly_sql -
    # comparte el presupuesto con las consultas SQL (RF-022/RF-032): un
    # post-proceso Polars sigue siendo trabajo que un LLM en loop podria
    # repetir sin limite si no contara para el mismo tope.
    if ctx.deps.query_count >= ctx.deps.max_queries_per_run:
        await _record_tool_call(
            ctx.deps,
            tool="run_analysis",
            input_payload={"group_by": group_by, "agg": agg},
            start=start,
            status=ToolCallStatus.ERROR,
            error_message="Limite de consultas por analisis alcanzado",
        )
        return (
            f"ERROR: ya alcanzaste el limite de {ctx.deps.max_queries_per_run} "
            "consultas/analisis para este analisis - respondé con lo que ya obtuviste."
        )
    ctx.deps.query_count += 1

    input_payload = {"group_by": group_by, "agg": agg, "sort_by": sort_by, "limit": limit}

    if ctx.deps.last_full_result is None:
        await _record_tool_call(
            ctx.deps,
            tool="run_analysis",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message="No hay ningun resultado previo para analizar",
        )
        return "ERROR: llama a execute_readonly_sql primero, run_analysis opera sobre su resultado"

    last = ctx.deps.last_full_result
    available = set(last["columns"])
    invalid_group_by = [c for c in group_by if c not in available]
    invalid_agg = [c for c in agg if c not in available]
    invalid_funcs = [f for f in agg.values() if f not in _AGG_FUNCS]
    if invalid_group_by or invalid_agg or invalid_funcs:
        errors = []
        if invalid_group_by:
            errors.append(f"columnas de group_by inexistentes: {invalid_group_by}")
        if invalid_agg:
            errors.append(f"columnas de agg inexistentes: {invalid_agg}")
        if invalid_funcs:
            errors.append(
                f"funciones de agg no permitidas: {invalid_funcs} (uso: {sorted(_AGG_FUNCS)})"
            )
        message = "; ".join(errors)
        await _record_tool_call(
            ctx.deps,
            tool="run_analysis",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=message,
        )
        return f"ERROR: {message}. Columnas disponibles: {sorted(available)}"

    try:
        df = pl.DataFrame(last["rows"], schema=last["columns"], orient="row")
        agg_exprs = [
            getattr(pl.col(col), func)().alias(f"{col}_{func}") for col, func in agg.items()
        ]
        result_df = df.group_by(group_by).agg(agg_exprs) if group_by else df.select(agg_exprs)
        if sort_by:
            if sort_by not in result_df.columns:
                raise ValueError(f"sort_by '{sort_by}' no es una columna del resultado")
            result_df = result_df.sort(sort_by, descending=descending)
        limit_truncated = False
        if limit is not None:
            capped_limit = min(limit, ctx.deps.max_rows)
            limit_truncated = result_df.height > capped_limit
            result_df = result_df.head(capped_limit)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de Polars es un error de negocio, no de la plataforma
        await _record_tool_call(
            ctx.deps,
            tool="run_analysis",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=str(exc),
        )
        await publish_event(
            ctx.deps.analysis_id, {"type": "tool_call", "tool": "run_analysis", "status": "ERROR"}
        )
        return f"ERROR: fallo al procesar con Polars: {exc}"

    result_rows = result_df.rows()
    result_columns = result_df.columns
    # `truncated` se propaga del resultado de entrada (si la consulta SQL
    # original ya estaba incompleta - mas alla de max_rows en Postgres- la
    # agregacion tambien lo esta, aunque Polars corra sobre TODO lo que
    # recibio) mas cualquier truncamiento propio que haya hecho `limit`.
    truncated = last["truncated"] or limit_truncated
    summary = {
        "columns": result_columns,
        "row_count": len(result_rows),
        "truncated": truncated,
    }
    await _record_tool_call(
        ctx.deps,
        tool="run_analysis",
        input_payload=input_payload,
        start=start,
        status=ToolCallStatus.SUCCESS,
        output_summary=summary,
    )
    await publish_event(
        ctx.deps.analysis_id, {"type": "tool_call", "tool": "run_analysis", "status": "SUCCESS"}
    )

    query_label = f"[polars] group_by={group_by} agg={agg}"
    evidence_rows = result_rows[:_EVIDENCE_ROW_CAP]
    ctx.deps.results.append(
        {
            "sql": query_label,
            **summary,
            "rows": evidence_rows,
            "evidence_truncated": len(result_rows) > _EVIDENCE_ROW_CAP,
        }
    )
    # Encadenamiento: si el modelo llama run_analysis o create_chart de
    # nuevo, deben operar sobre ESTE resultado completo (no la muestra de
    # evidencia) - mismo motivo que en execute_readonly_sql.
    ctx.deps.last_full_result = {
        "sql": query_label,
        "columns": result_columns,
        "rows": result_rows,
        "truncated": truncated,
    }

    return json.dumps(
        {
            "columns": result_columns,
            "rows": evidence_rows,
            "row_count": len(result_rows),
            "truncated": truncated,
        }
    )


async def create_chart(
    ctx: RunContext[AgentDeps],
    chart_type: str,
    x_field: str,
    y_field: str,
    title: str,
) -> str:
    """RF-041: genera una especificacion de grafico (tipo, ejes, datos) a
    partir del resultado de la ULTIMA consulta/analisis exitoso - no
    ejecuta SQL nuevo ni renderiza una imagen, un frontend con Recharts
    consume la especificacion. Llama primero a execute_readonly_sql (o
    run_analysis). chart_type: bar, line, pie o scatter."""
    start = time.monotonic()

    if ctx.deps.chart_count >= ctx.deps.max_charts_per_run:
        await _record_tool_call(
            ctx.deps,
            tool="create_chart",
            input_payload={"chart_type": chart_type, "x_field": x_field, "y_field": y_field},
            start=start,
            status=ToolCallStatus.ERROR,
            error_message="Limite de graficos por analisis alcanzado",
        )
        return (
            f"ERROR: ya alcanzaste el limite de {ctx.deps.max_charts_per_run} "
            "graficos para este analisis"
        )
    ctx.deps.chart_count += 1

    input_payload = {
        "chart_type": chart_type,
        "x_field": x_field,
        "y_field": y_field,
        "title": title,
    }

    if chart_type not in _CHART_TYPES:
        await _record_tool_call(
            ctx.deps,
            tool="create_chart",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=f"chart_type invalido: {chart_type}",
        )
        return f"ERROR: chart_type debe ser uno de {sorted(_CHART_TYPES)}"

    if ctx.deps.last_full_result is None:
        await _record_tool_call(
            ctx.deps,
            tool="create_chart",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message="No hay ningun resultado previo para graficar",
        )
        return (
            "ERROR: llama a execute_readonly_sql (o run_analysis) primero, "
            "create_chart grafica su resultado"
        )

    last = ctx.deps.last_full_result
    available = set(last["columns"])
    if x_field not in available or y_field not in available:
        message = f"x_field/y_field deben ser columnas del ultimo resultado: {sorted(available)}"
        await _record_tool_call(
            ctx.deps,
            tool="create_chart",
            input_payload=input_payload,
            start=start,
            status=ToolCallStatus.ERROR,
            error_message=message,
        )
        return f"ERROR: {message}"

    # `last["rows"]` es el resultado COMPLETO (last_full_result, hasta
    # max_rows) - se calcula el x_field/y_field sobre eso, pero lo que se
    # persiste en spec_json (JSONB) se acota igual que la evidencia de
    # execute_readonly_sql, con el mismo motivo (.claude/rules/database.md).
    # `data_truncated` deja explicito que el grafico es una muestra, no
    # todo el resultado - antes se perdia esa distincion en silencio.
    chart_rows = last["rows"][:_EVIDENCE_ROW_CAP]
    spec = {
        "chart_type": chart_type,
        "title": title,
        "x_field": x_field,
        "y_field": y_field,
        "data": [dict(zip(last["columns"], row, strict=True)) for row in chart_rows],
        "data_truncated": len(last["rows"]) > _EVIDENCE_ROW_CAP,
    }
    artifact = AnalysisArtifact(
        analysis_id=ctx.deps.analysis_id,
        type=ArtifactType.CHART,
        spec_json=spec,
        source_sql=last["sql"],
    )
    ctx.deps.db.add(artifact)
    await ctx.deps.db.flush()

    await _record_tool_call(
        ctx.deps,
        tool="create_chart",
        input_payload=input_payload,
        start=start,
        status=ToolCallStatus.SUCCESS,
        output_summary={"artifact_id": str(artifact.id), "chart_type": chart_type},
    )
    await publish_event(
        ctx.deps.analysis_id, {"type": "tool_call", "tool": "create_chart", "status": "SUCCESS"}
    )

    return json.dumps({"artifact_id": str(artifact.id), "chart_type": chart_type, "title": title})
