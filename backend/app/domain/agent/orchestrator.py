import asyncio
import uuid
from datetime import UTC, datetime

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.agent_run import AgentRun, AgentRunStatus
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.dataset import Dataset
from app.domain.agent.deps import AgentDeps
from app.domain.agent.tools import execute_readonly_sql, inspect_schema
from app.domain.datasets.schemas import ColumnSchema

SYSTEM_PROMPT = """
Sos un analista de datos. Tenes acceso a un unico dataset a traves de dos
herramientas: inspect_schema (columnas y tipos disponibles) y
execute_readonly_sql (UNA consulta SELECT de solo lectura sobre ese
dataset). Llama siempre primero a inspect_schema antes de escribir SQL.
No inventes ni intentes acceder a ninguna otra tabla. Si una consulta es
rechazada, corregila segun el motivo del error en vez de repetirla igual.
Respondé la pregunta del usuario en espanol, de forma breve, basandote
solo en los resultados que efectivamente obtuviste - no inventes datos.
""".strip()


class AnalysisExecutionError(Exception):
    pass


def _build_model() -> OpenAIChatModel:
    return OpenAIChatModel(
        settings.llm_model,
        provider=OpenAIProvider(base_url=settings.llm_base_url, api_key=settings.llm_api_key),
    )


def build_agent(model: OpenAIChatModel | None = None) -> Agent[AgentDeps, str]:
    """Separado de run_analysis para que los tests puedan inyectar un
    modelo de prueba (TestModel/FunctionModel) sin tocar config real."""
    return Agent(
        model or _build_model(),
        deps_type=AgentDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
        tools=[inspect_schema, execute_readonly_sql],
    )


async def run_analysis(
    db: AsyncSession,
    *,
    analysis: Analysis,
    dataset: Dataset,
    agent: Agent[AgentDeps, str] | None = None,
) -> None:
    """Orquesta pregunta -> schema -> SQL -> resultado (RF-020 a RF-024).

    Corre sincronicamente dentro del request (misma decision que datasets
    import en Fase 2 - ver docs/architecture.md seccion 12). Deja el
    Analysis en un estado terminal (COMPLETED/FAILED/TIMED_OUT) siempre,
    nunca colgado en un estado intermedio (RF-025).
    """
    analysis.status = AnalysisStatus.PLANNING
    await db.flush()

    trace_id = uuid.uuid4().hex
    agent_run = AgentRun(
        analysis_id=analysis.id,
        model=settings.llm_model or "unknown",
        status=AgentRunStatus.RUNNING,
        trace_id=trace_id,
    )
    db.add(agent_run)
    await db.flush()

    columns = [ColumnSchema(**column) for column in dataset.schema_json]
    deps = AgentDeps(
        db=db,
        agent_run_id=agent_run.id,
        dataset_id=dataset.id,
        table_name=f"datasets.{dataset.table_name}",
        columns=columns,
        max_rows=settings.agent_sql_max_rows,
    )

    analysis.status = AnalysisStatus.TOOL_RUNNING
    await db.flush()

    overall_timeout = settings.agent_sql_timeout_seconds * 4

    try:
        # build_agent() tambien puede fallar (ej. LLM_API_KEY sin
        # configurar) - tiene que quedar DENTRO del try, si no ese error
        # se escapa de run_analysis como una excepcion no manejada y el
        # endpoint devuelve 500 en vez de dejar el analysis en FAILED.
        active_agent = agent or build_agent()
        result = await asyncio.wait_for(
            active_agent.run(analysis.question, deps=deps), timeout=overall_timeout
        )
    except TimeoutError:
        agent_run.status = AgentRunStatus.FAILED
        agent_run.finished_at = datetime.now(UTC)
        analysis.status = AnalysisStatus.TIMED_OUT
        analysis.error = "La ejecucion supero el tiempo maximo permitido"
        await db.commit()
        return
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del agente termina el analysis, no lo cuelga
        agent_run.status = AgentRunStatus.FAILED
        agent_run.finished_at = datetime.now(UTC)
        analysis.status = AnalysisStatus.FAILED
        analysis.error = str(exc)
        await db.commit()
        return

    analysis.status = AnalysisStatus.GENERATING_RESPONSE
    analysis.answer = result.output
    analysis.result_json = deps.last_result
    analysis.status = AnalysisStatus.COMPLETED
    agent_run.status = AgentRunStatus.COMPLETED
    agent_run.finished_at = datetime.now(UTC)
    await db.commit()
