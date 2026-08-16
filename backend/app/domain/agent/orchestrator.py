import asyncio
import logging
import uuid
from datetime import UTC, datetime

from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.agent_run import AgentRun, AgentRunStatus
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.dataset import Dataset
from app.domain.agent.deps import AgentDeps
from app.domain.agent.events import publish_event
from app.domain.agent.tools import create_chart, execute_readonly_sql, inspect_schema
from app.domain.agent.tools import run_analysis as run_analysis_tool
from app.domain.datasets.schemas import ColumnSchema

logger = logging.getLogger("app.agent")

SYSTEM_PROMPT = """
Sos un analista de datos. Tenes acceso a un unico dataset a traves de
estas herramientas:
- inspect_schema: columnas y tipos disponibles. Llamala siempre primero,
  antes de escribir SQL.
- execute_readonly_sql: una consulta SELECT de solo lectura sobre el
  dataset.
- run_analysis: post-procesa (agrupa/agrega/ordena) el resultado de la
  ULTIMA consulta exitosa con Polars, para pivots o rankings que una
  unica consulta SQL no resuelve comodo. No reemplaza a execute_readonly_sql,
  la complementa.
- create_chart: genera la especificacion de un grafico (no una imagen) a
  partir del ultimo resultado, si la pregunta se beneficia de una
  visualizacion ademas de la respuesta en texto.

Para preguntas simples, una sola consulta alcanza. Para preguntas
complejas que requieran investigar mas de un angulo (comparar periodos,
formular una hipotesis y verificarla, etc.) podes llamar a
execute_readonly_sql o run_analysis varias veces - hay un limite de
consultas por analisis, asi que priorizá las que mas aportan a la
respuesta en vez de tantear al azar. No inventes ni intentes acceder a
ninguna otra tabla. Si una consulta es rechazada, corregila segun el
motivo del error en vez de repetirla igual. Respondé la pregunta del
usuario en espanol, de forma breve, basandote solo en los resultados que
efectivamente obtuviste - no inventes datos.
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
    modelo de prueba (TestModel/FunctionModel) sin tocar config real.

    execute_readonly_sql, run_analysis y create_chart van con
    sequential=True: el default de pydantic-ai (y de la API de OpenAI-
    compatible) permite que el modelo emita varias tool calls del mismo
    turno y se ejecuten en paralelo - eso rompería los presupuestos
    compartidos (query_count para RF-022/RF-040, chart_count para RF-041)
    si no fuera porque tools.py ya los reserva de forma atomica y
    sincronica, antes de cualquier `await`. Esto es una segunda capa de
    defensa, no la unica - las tres tools tienen el mismo tratamiento por
    consistencia, aunque solo execute_readonly_sql/run_analysis comparten
    presupuesto entre si.
    """
    return Agent(
        model or _build_model(),
        deps_type=AgentDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            inspect_schema,
            Tool(execute_readonly_sql, sequential=True),
            Tool(run_analysis_tool, name="run_analysis", sequential=True),
            Tool(create_chart, sequential=True),
        ],
    )


async def _set_status(db: AsyncSession, analysis: Analysis, status: AnalysisStatus) -> None:
    analysis.status = status
    await db.flush()
    await publish_event(analysis.id, {"type": "status", "status": status.value})


async def run_analysis(
    db: AsyncSession,
    *,
    analysis: Analysis,
    dataset: Dataset,
    agent: Agent[AgentDeps, str] | None = None,
) -> None:
    """Orquesta pregunta -> schema -> SQL(es) -> resultado (RF-020 a RF-025).

    Fase 4: corre dentro de un job de workers/ (ARQ), no sincronico en el
    request (ver workers/tasks/analysis.py) - esto permite cancelacion
    real (RF-025, via arq Job.abort()) y progreso en vivo por SSE
    (publish_event). Deja el Analysis en un estado terminal (COMPLETED/
    FAILED/TIMED_OUT/CANCELLED) siempre, nunca colgado en un estado
    intermedio.
    """
    await _set_status(db, analysis, AnalysisStatus.PLANNING)

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
        analysis_id=analysis.id,
        agent_run_id=agent_run.id,
        dataset_id=dataset.id,
        table_name=f"datasets.{dataset.table_name}",
        columns=columns,
        max_rows=settings.agent_sql_max_rows,
        max_joins=settings.agent_sql_max_joins,
        max_subqueries=settings.agent_sql_max_subqueries,
        max_queries_per_run=settings.agent_max_queries_per_run,
        max_charts_per_run=settings.agent_max_charts_per_run,
    )

    await _set_status(db, analysis, AnalysisStatus.TOOL_RUNNING)

    logger.info(
        "agent_run.start trace_id=%s analysis_id=%s dataset_id=%s model=%s",
        trace_id,
        analysis.id,
        dataset.id,
        agent_run.model,
    )

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
        logger.warning("agent_run.timed_out trace_id=%s analysis_id=%s", trace_id, analysis.id)
        await db.commit()
        await publish_event(analysis.id, {"type": "status", "status": analysis.status.value})
        return
    except asyncio.CancelledError:
        # RF-025: llega aca cuando arq Job.abort() cancela el asyncio task
        # que corre este job (workers/tasks/analysis.py). A diferencia de
        # TimeoutError/Exception, CancelledError es un BaseException - no
        # lo captura el "except Exception" de abajo, y hay que re-lanzarlo
        # despues de dejar el estado consistente para que ARQ lo registre
        # como abortado, no como completado.
        agent_run.status = AgentRunStatus.CANCELLED
        agent_run.finished_at = datetime.now(UTC)
        analysis.status = AnalysisStatus.CANCELLED
        analysis.error = "Analisis cancelado por el usuario"
        logger.warning("agent_run.cancelled trace_id=%s analysis_id=%s", trace_id, analysis.id)
        await db.commit()
        await publish_event(analysis.id, {"type": "status", "status": analysis.status.value})
        raise
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del agente termina el analysis, no lo cuelga
        agent_run.status = AgentRunStatus.FAILED
        agent_run.finished_at = datetime.now(UTC)
        analysis.status = AnalysisStatus.FAILED
        # GET /analyses/{id} expone `error` a cualquier miembro de la
        # organizacion (incluido VIEWER), asi que nunca puede ser str(exc)
        # crudo - errores no anticipados (cliente LLM, driver, etc.) pueden
        # traer detalles internos (URLs, hosts, fragmentos de config). El
        # detalle real solo va al log server-side.
        analysis.error = (
            f"Ocurrio un error inesperado al ejecutar el analisis (trace_id={trace_id})"
        )
        logger.error(
            "agent_run.failed trace_id=%s analysis_id=%s error=%r",
            trace_id,
            analysis.id,
            exc,
            exc_info=True,
        )
        await db.commit()
        await publish_event(analysis.id, {"type": "status", "status": analysis.status.value})
        return

    await _set_status(db, analysis, AnalysisStatus.GENERATING_RESPONSE)
    analysis.answer = result.output
    analysis.result_json = deps.results or None
    analysis.status = AnalysisStatus.COMPLETED
    agent_run.status = AgentRunStatus.COMPLETED
    agent_run.finished_at = datetime.now(UTC)
    logger.info("agent_run.completed trace_id=%s analysis_id=%s", trace_id, analysis.id)
    await db.commit()
    await publish_event(analysis.id, {"type": "status", "status": analysis.status.value})
