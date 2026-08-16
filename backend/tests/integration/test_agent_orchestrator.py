import asyncio
import io
import uuid

import pytest
from app.db.models.agent_run import AgentRun, AgentRunStatus
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.dataset import Dataset
from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.domain.agent.orchestrator import build_agent, run_analysis
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel
from sqlalchemy import select


def _seen_tools(messages: list) -> list[str]:
    return [
        part.tool_name
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


def _happy_path_script(query: str, table_name: str):
    def script(messages, _info):
        seen = _seen_tools(messages)
        if "inspect_schema" not in seen:
            return ModelResponse(parts=[ToolCallPart(tool_name="inspect_schema", args={})])
        if "execute_readonly_sql" not in seen:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="execute_readonly_sql",
                        args={"sql": f"SELECT * FROM {table_name} {query}"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Listo, ahi esta el resultado.")])

    return script


def _malicious_script(table_name: str):
    """Simula un LLM que intenta leer una tabla que no le corresponde."""

    def script(messages, _info):
        seen = _seen_tools(messages)
        if "execute_readonly_sql" not in seen:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="execute_readonly_sql",
                        args={"sql": "SELECT * FROM public.users"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="No pude acceder a esos datos.")])

    return script


async def _register_and_import(client, unique_email: str):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "correcthorsebattery",
            "organization_name": "Agent Test Org",
        },
    )
    body = register_response.json()
    token = body["access_token"]
    org_id = body["user"]["memberships"][0]["organization_id"]
    user_id = body["user"]["id"]

    csv_content = "product,units\nWidget A,120\nWidget B,45\n"
    import_response = await client.post(
        "/api/v1/datasets/import",
        data={"organization_id": org_id},
        files={"file": ("dataset.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = import_response.json()["id"]
    return org_id, user_id, dataset_id


class TestOrchestratorHappyPath:
    async def test_agent_inspects_schema_then_queries_and_completes(
        self, client, db_session, unique_email
    ):
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)

        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Cuantas unidades hay de cada producto?",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        table_name = f"datasets.{dataset.table_name}"
        agent = build_agent(FunctionModel(_happy_path_script("", table_name)))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.answer
        assert analysis.result_json is not None
        assert analysis.result_json[0]["row_count"] == 2

        agent_run = (
            await db_session.execute(select(AgentRun).where(AgentRun.analysis_id == analysis.id))
        ).scalar_one()
        assert agent_run.status == AgentRunStatus.COMPLETED
        assert agent_run.trace_id

        tool_calls = (
            (
                await db_session.execute(
                    select(ToolCall).where(ToolCall.agent_run_id == agent_run.id)
                )
            )
            .scalars()
            .all()
        )
        tool_names = {tc.tool for tc in tool_calls}
        assert tool_names == {"inspect_schema", "execute_readonly_sql"}
        assert all(tc.status == ToolCallStatus.SUCCESS for tc in tool_calls)


def _multi_query_script(table_name: str, query_count: int):
    def script(messages, _info):
        seen = _seen_tools(messages)
        if "inspect_schema" not in seen:
            return ModelResponse(parts=[ToolCallPart(tool_name="inspect_schema", args={})])
        executed = seen.count("execute_readonly_sql")
        if executed < query_count:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="execute_readonly_sql",
                        args={
                            "sql": f"SELECT COUNT(*) AS n FROM {table_name} -- consulta {executed}"
                        },
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Listo, investigue varias consultas.")])

    return script


class TestOrchestratorMultiQuery:
    async def test_agent_can_run_more_than_one_query_for_a_complex_question(
        self, client, db_session, unique_email
    ):
        """RF-022: el agente puede ejecutar mas de una consulta por
        pregunta - cada una queda como evidencia separada en result_json,
        no se pisan entre si."""
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta compleja que necesita varias consultas",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        table_name = f"datasets.{dataset.table_name}"
        agent = build_agent(FunctionModel(_multi_query_script(table_name, query_count=3)))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.result_json is not None
        assert len(analysis.result_json) == 3

    async def test_agent_is_stopped_at_the_query_budget(self, client, db_session, unique_email):
        """RF-022 sin limite seria un vector de costo/DoS nuevo (un LLM en
        loop) - execute_readonly_sql rechaza pasado
        settings.agent_max_queries_per_run (default 5), sin colgar el
        analysis."""
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta que intenta abusar del presupuesto de consultas",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        table_name = f"datasets.{dataset.table_name}"
        # Pide 10 consultas, muy por encima del default de 5.
        agent = build_agent(FunctionModel(_multi_query_script(table_name, query_count=10)))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.result_json is not None
        assert len(analysis.result_json) == 5

        agent_run = (
            await db_session.execute(select(AgentRun).where(AgentRun.analysis_id == analysis.id))
        ).scalar_one()
        sql_calls = (
            (
                await db_session.execute(
                    select(ToolCall).where(
                        ToolCall.agent_run_id == agent_run.id,
                        ToolCall.tool == "execute_readonly_sql",
                    )
                )
            )
            .scalars()
            .all()
        )
        # El script intento 10 veces - 5 exitosas (el limite) + 5 rechazadas
        # por presupuesto agotado, ninguna se cuela de mas.
        assert len(sql_calls) == 10
        assert sum(1 for tc in sql_calls if tc.status == ToolCallStatus.SUCCESS) == 5
        assert sum(1 for tc in sql_calls if tc.status == ToolCallStatus.ERROR) == 5


def _parallel_query_script(table_name: str, calls_in_one_turn: int):
    """Simula un modelo que emite VARIAS tool calls de execute_readonly_sql
    en un mismo turno (comportamiento normal de function-calling paralelo,
    no requiere prompt injection) - esto es lo que exponia la condicion de
    carrera del presupuesto de consultas antes del fix."""

    def script(messages, _info):
        seen = _seen_tools(messages)
        if "inspect_schema" not in seen:
            return ModelResponse(parts=[ToolCallPart(tool_name="inspect_schema", args={})])
        if seen.count("execute_readonly_sql") == 0:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="execute_readonly_sql",
                        args={"sql": f"SELECT {i} AS n"},
                    )
                    for i in range(calls_in_one_turn)
                ]
            )
        return ModelResponse(parts=[TextPart(content="Listo.")])

    return script


class TestOrchestratorConcurrentToolCalls:
    async def test_query_budget_holds_even_with_many_tool_calls_in_a_single_turn(
        self, client, db_session, unique_email
    ):
        """Regresion de seguridad: un modelo puede emitir N tool calls de
        execute_readonly_sql en UN SOLO turno (function-calling paralelo,
        default de la API). Antes del fix, el chequeo del presupuesto
        (`len(ctx.deps.results) >= max_queries_per_run`) leia un valor
        stale porque el append pasaba DESPUES del round-trip a Postgres -
        las N llamadas concurrentes veian todas 0 y se saltaban el limite
        por completo. Ahora la reserva (`ctx.deps.query_count`) es
        sincronica, antes de cualquier await."""
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta que intenta pedir todo de una",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        table_name = f"datasets.{dataset.table_name}"
        # 20 tool calls en UN turno, muy por encima del default de 5.
        agent = build_agent(FunctionModel(_parallel_query_script(table_name, calls_in_one_turn=20)))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.result_json is not None
        assert len(analysis.result_json) == 5

        agent_run = (
            await db_session.execute(select(AgentRun).where(AgentRun.analysis_id == analysis.id))
        ).scalar_one()
        sql_calls = (
            (
                await db_session.execute(
                    select(ToolCall).where(
                        ToolCall.agent_run_id == agent_run.id,
                        ToolCall.tool == "execute_readonly_sql",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sum(1 for tc in sql_calls if tc.status == ToolCallStatus.SUCCESS) == 5


class TestOrchestratorCancellation:
    async def test_cancelling_the_task_leaves_analysis_cancelled_not_stuck(
        self, client, db_session, unique_email
    ):
        """RF-025: cuando arq Job.abort() cancela el asyncio task que corre
        run_analysis (simulado aca cancelando el task directamente, sin
        pasar por ARQ/Redis), el analysis debe quedar en CANCELLED, no
        colgado en un estado intermedio."""
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta cualquiera",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        async def slow_script(_messages, _info):
            await asyncio.sleep(2)
            return ModelResponse(parts=[TextPart(content="no deberia llegar aca")])

        agent = build_agent(FunctionModel(slow_script))
        task = asyncio.create_task(
            run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)
        )
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert analysis.status == AnalysisStatus.CANCELLED
        assert analysis.error

        agent_run = (
            await db_session.execute(select(AgentRun).where(AgentRun.analysis_id == analysis.id))
        ).scalar_one()
        assert agent_run.status == AgentRunStatus.CANCELLED
        assert agent_run.finished_at is not None


class TestOrchestratorBlocksTenantCrossover:
    async def test_agent_trying_to_read_another_table_is_blocked_and_audited(
        self, client, db_session, unique_email
    ):
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)

        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Dame los emails de los usuarios",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        agent = build_agent(FunctionModel(_malicious_script(dataset.table_name)))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        # El analysis igual termina COMPLETED (el agente recibe el error y
        # responde con texto) - lo que importa es que la tool call quedo
        # marcada como ERROR y nunca se ejecuto la consulta no autorizada.
        agent_run = (
            await db_session.execute(select(AgentRun).where(AgentRun.analysis_id == analysis.id))
        ).scalar_one()
        tool_calls = (
            (
                await db_session.execute(
                    select(ToolCall).where(ToolCall.agent_run_id == agent_run.id)
                )
            )
            .scalars()
            .all()
        )
        sql_calls = [tc for tc in tool_calls if tc.tool == "execute_readonly_sql"]
        assert len(sql_calls) == 1
        assert sql_calls[0].status == ToolCallStatus.ERROR
        assert "no autorizadas" in sql_calls[0].error_message
        # Nunca se guardo evidencia de una consulta que jamas se ejecuto.
        assert analysis.result_json is None


class TestOrchestratorHandlesAgentFailure:
    async def test_model_error_leaves_analysis_in_failed_not_stuck(
        self, client, db_session, unique_email
    ):
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta cualquiera",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        def broken_script(_messages, _info):
            raise RuntimeError("el proveedor de LLM no respondio")

        agent = build_agent(FunctionModel(broken_script))
        await run_analysis(db_session, analysis=analysis, dataset=dataset, agent=agent)

        assert analysis.status == AnalysisStatus.FAILED
        assert analysis.error

    async def test_missing_llm_config_leaves_analysis_failed_not_500(
        self, client, db_session, unique_email
    ):
        """Reproduce el bug real encontrado probando contra Docker: sin
        agent= explicito, run_analysis intenta construir el agente real
        con la config de LLM del entorno de test (vacia a proposito - ver
        conftest.py) - build_agent() fallando DEBE terminar en FAILED, no
        propagar la excepcion sin manejar (eso era un 500 en el endpoint)."""
        org_id, user_id, dataset_id = await _register_and_import(client, unique_email)
        dataset = (
            await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
        ).scalar_one()

        analysis = Analysis(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            dataset_id=dataset.id,
            question="Pregunta cualquiera",
            status=AnalysisStatus.QUEUED,
        )
        db_session.add(analysis)
        await db_session.flush()

        await run_analysis(db_session, analysis=analysis, dataset=dataset)

        assert analysis.status == AnalysisStatus.FAILED
        assert analysis.error
