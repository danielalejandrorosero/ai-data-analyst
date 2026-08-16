import io
import uuid

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
        assert analysis.result_json["row_count"] == 2

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
