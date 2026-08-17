import io
import uuid

import pytest
from app.core.config import settings
from app.db.models.agent_run import AgentRun, AgentRunStatus
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.dataset import Dataset
from app.db.models.membership import Membership, Role
from app.db.models.tool_call import ToolCall, ToolCallStatus
from sqlalchemy import select


@pytest.fixture(autouse=True)
def _stub_arq(monkeypatch):
    """Los tests de este archivo verifican el endpoint HTTP (RBAC, 404,
    forma de la respuesta) - la orquestacion real del agente ya tiene su
    propia cobertura en test_agent_orchestrator.py contra la capa de
    servicio directamente, y el job de ARQ en si mismo es un wrapper fino
    (workers/tasks/analysis.py) sin logica propia que testear aca. Mockear
    evita que el endpoint necesite un worker real corriendo ni un
    LLM_API_KEY en el entorno de test."""
    import app.api.analyses as analyses_module
    import app.domain.agent.cancellation as cancellation_module

    class _FakeJob:
        def __init__(self, job_id: str):
            self.job_id = job_id

    class _FakePool:
        async def enqueue_job(self, _function_name, *_args):
            return _FakeJob(job_id=f"fake-job-{uuid.uuid4().hex}")

    async def _fake_get_arq_pool():
        return _FakePool()

    async def _fake_abort(self, *args, **kwargs):  # noqa: ARG001
        return True

    monkeypatch.setattr(analyses_module, "get_arq_pool", _fake_get_arq_pool)
    monkeypatch.setattr(cancellation_module.Job, "abort", _fake_abort)


async def _register_and_import(client, unique_email: str):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "correcthorsebattery",
            "organization_name": "Analyses Test Org",
        },
    )
    body = register_response.json()
    token = body["access_token"]
    org_id = body["user"]["memberships"][0]["organization_id"]

    import_response = await client.post(
        "/api/datasets/import",
        data={"organization_id": org_id},
        files={"file": ("d.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = import_response.json()["id"]
    return token, org_id, dataset_id


async def _import_csv(client, token: str, org_id: str, *, filename: str, content: bytes) -> str:
    """Como _register_and_import pero con contenido de CSV a medida y
    reusando una org/token existente - usado por los tests de export que
    necesitan un dataset real con mas de _EVIDENCE_ROW_CAP (100) filas
    para probar la re-ejecucion (RF-043)."""
    import_response = await client.post(
        "/api/datasets/import",
        data={"organization_id": org_id},
        files={"file": (filename, io.BytesIO(content), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return import_response.json()["id"]


async def _qualified_table_name(db_session, dataset_id: str) -> str:
    dataset = (
        await db_session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id)))
    ).scalar_one()
    return f"datasets.{dataset.table_name}"


async def _set_status_directly(db_session, analysis_id: str, status: AnalysisStatus) -> None:
    """Simula que el worker (nunca corre de verdad en estos tests, ver
    _stub_arq) ya termino de procesar el job."""
    analysis = (
        await db_session.execute(select(Analysis).where(Analysis.id == uuid.UUID(analysis_id)))
    ).scalar_one()
    analysis.status = status
    await db_session.commit()


async def _set_result_directly(db_session, analysis_id: str, result_json: list[dict]) -> None:
    """Simula la evidencia que run_analysis_job hubiera dejado (ver
    _stub_arq - el worker nunca corre de verdad en estos tests)."""
    analysis = (
        await db_session.execute(select(Analysis).where(Analysis.id == uuid.UUID(analysis_id)))
    ).scalar_one()
    analysis.status = AnalysisStatus.COMPLETED
    analysis.result_json = result_json
    await db_session.commit()


async def _add_artifact_directly(db_session, analysis_id: str, **overrides) -> str:
    from app.db.models.analysis_artifact import AnalysisArtifact, ArtifactType

    artifact = AnalysisArtifact(
        analysis_id=uuid.UUID(analysis_id),
        type=overrides.get("type", ArtifactType.CHART),
        spec_json=overrides.get(
            "spec_json",
            {"chart_type": "bar", "title": "x", "x_field": "a", "y_field": "b", "data": []},
        ),
        source_sql=overrides.get("source_sql", "SELECT * FROM datasets.ds_x"),
    )
    db_session.add(artifact)
    await db_session.commit()
    return str(artifact.id)


async def _add_tool_call_directly(db_session, analysis_id: str, **overrides) -> str:
    """Simula lo que _record_tool_call (domain/agent/tools.py) hubiera
    dejado durante una corrida real - el worker nunca corre de verdad en
    estos tests (ver _stub_arq)."""
    agent_run = AgentRun(
        analysis_id=uuid.UUID(analysis_id),
        model="test-model",
        status=AgentRunStatus.COMPLETED,
        trace_id=f"trace-{uuid.uuid4().hex}",
    )
    db_session.add(agent_run)
    await db_session.flush()

    tool_call = ToolCall(
        agent_run_id=agent_run.id,
        tool=overrides.get("tool", "execute_readonly_sql"),
        input_json=overrides.get("input_json", {"sql": "SELECT secret_value FROM datasets.ds_x"}),
        input_hash=overrides.get("input_hash", "deadbeef"),
        status=overrides.get("status", ToolCallStatus.SUCCESS),
        error_message=overrides.get("error_message"),
        duration_ms=overrides.get("duration_ms", 42),
    )
    db_session.add(tool_call)
    await db_session.commit()
    return str(tool_call.id)


class TestCreateAnalysis:
    async def test_analyst_can_create_analysis(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "Cuantas filas hay?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "QUEUED"
        assert body["answer"] is None

    async def test_create_analysis_without_token_is_rejected(self, client, unique_email):
        _token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/analyses", json={"dataset_id": dataset_id, "question": "x"}
        )
        assert response.status_code == 401

    async def test_create_analysis_for_unknown_dataset_returns_404(self, client, unique_email):
        token, _org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/analyses",
            json={"dataset_id": str(uuid.uuid4()), "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_create_analysis_for_dataset_without_membership_returns_404(
        self, client, unique_email
    ):
        _token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404

    async def test_viewer_cannot_create_analysis(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        viewer_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"viewer-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Viewer Org",
            },
        )
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]

        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403


class TestGetAnalysis:
    async def test_owner_can_fetch_their_analysis(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.get(
            f"/api/analyses/{analysis_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["id"] == analysis_id

    async def test_get_analysis_without_token_is_rejected(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.get(f"/api/analyses/{analysis_id}")
        assert response.status_code == 401

    async def test_get_analysis_of_another_organization_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        other_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"other-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Other Org",
            },
        )
        other_token = other_response.json()["access_token"]

        response = await client.get(
            f"/api/analyses/{analysis_id}", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert response.status_code == 404

    async def test_get_unknown_analysis_returns_404(self, client, unique_email):
        token, _org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.get(
            f"/api/analyses/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404


class TestListAnalyses:
    async def test_lists_analyses_of_the_caller_organization_newest_first(
        self, client, unique_email
    ):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        first = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "primera"},
            headers={"Authorization": f"Bearer {token}"},
        )
        second = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "segunda"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            "/api/analyses",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body] == [
            second.json()["id"],
            first.json()["id"],
        ]
        # Version liviana: sin tool_calls ni result completo.
        assert "tool_calls" not in body[0]

    async def test_viewer_can_list_analyses(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )

        viewer_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"viewer-list-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Viewer List Org",
            },
        )
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]
        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.get(
            "/api/analyses",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_listing_analyses_of_another_organization_returns_403(self, client, unique_email):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-list-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider List Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            "/api/analyses",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 403

    async def test_list_analyses_without_token_is_rejected(self, client, unique_email):
        _token, org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.get("/api/analyses", params={"organization_id": org_id})
        assert response.status_code == 401


class TestCancelAnalysis:
    async def test_analyst_can_cancel_a_running_analysis(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancel_requested"

    async def test_successful_abort_leaves_analysis_cancelled_even_if_job_never_started(
        self, client, unique_email
    ):
        """Regresion real: si arq aborta el job ANTES de que el worker lo
        arranque (todavia en cola), run_analysis() nunca corre - nada mas
        deja el Analysis en CANCELLED, se quedaria colgado en QUEUED para
        siempre sin este fix. El stub de Job.abort() (_stub_arq) siempre
        devuelve True, simulando ese caso."""
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )

        get_response = await client.get(
            f"/api/analyses/{analysis_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert get_response.json()["status"] == "CANCELLED"

    async def test_arq_abort_raising_does_not_crash_the_endpoint(
        self, client, unique_email, monkeypatch
    ):
        """Regresion: Job.abort() puede lanzar asyncio.TimeoutError (si el
        polling interno de arq supera el timeout) u otra excepcion del job
        - antes del fix, ninguna de las dos estaba capturada y escalaba a
        un 500 sin traducir, contradiciendo la regla de que los errores de
        dominio se traducen a codigos HTTP explicitos."""
        import app.domain.agent.cancellation as cancellation_module

        async def _raise_timeout(self, *args, **kwargs):  # noqa: ARG001
            raise TimeoutError("arq no confirmo a tiempo")

        monkeypatch.setattr(cancellation_module.Job, "abort", _raise_timeout)

        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancel_requested"

    async def test_cancelling_a_terminal_analysis_returns_409(
        self, client, unique_email, db_session
    ):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_status_directly(db_session, analysis_id, AnalysisStatus.COMPLETED)

        response = await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_viewer_cannot_cancel(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        viewer_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"viewer-cancel-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Viewer Cancel Org",
            },
        )
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]
        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    async def test_cancelling_unknown_analysis_returns_404(self, client, unique_email):
        token, _org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            f"/api/analyses/{uuid.uuid4()}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_cancelling_without_membership_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-cancel-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Cancel Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.post(
            f"/api/analyses/{analysis_id}/cancel",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404


class TestStreamAnalysisEvents:
    async def test_terminal_analysis_streams_single_status_event_and_closes(
        self, client, unique_email, db_session
    ):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_status_directly(db_session, analysis_id, AnalysisStatus.COMPLETED)

        response = await client.get(
            f"/api/analyses/{analysis_id}/events",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "COMPLETED" in response.text

    async def test_stream_events_without_membership_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-events-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Events Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            f"/api/analyses/{analysis_id}/events",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404


class TestListArtifacts:
    async def test_lists_artifacts_created_for_the_analysis(self, client, unique_email, db_session):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        artifact_id = await _add_artifact_directly(
            db_session,
            analysis_id,
            spec_json={
                "chart_type": "bar",
                "title": "t",
                "x_field": "a",
                "y_field": "b",
                "data": [],
            },
            source_sql="SELECT a, b FROM datasets.ds_x",
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/artifacts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == artifact_id
        assert body[0]["type"] == "CHART"
        assert body[0]["spec"]["chart_type"] == "bar"
        assert body[0]["source_sql"] == "SELECT a, b FROM datasets.ds_x"

    async def test_viewer_can_list_artifacts(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _add_artifact_directly(db_session, analysis_id)

        viewer_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"viewer-artifacts-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Viewer Artifacts Org",
            },
        )
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]
        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.get(
            f"/api/analyses/{analysis_id}/artifacts",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_listing_artifacts_without_membership_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-artifacts-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Artifacts Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            f"/api/analyses/{analysis_id}/artifacts",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404


class TestExportAnalysisResult:
    async def test_export_json_returns_last_query_by_default(
        self, client, unique_email, db_session
    ):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        # Prefijo "[polars]" (run_analysis, no es SQL real): el export no
        # re-ejecuta nada, exporta la evidencia persistida tal cual - lo
        # que este test realmente cubre es la seleccion del ULTIMO
        # resultado por defecto, no la re-ejecucion (ver
        # TestExportAnalysisResult mas abajo para eso).
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "[polars] group_by=[] agg={}",
                    "columns": ["a"],
                    "rows": [[1]],
                    "row_count": 1,
                },
                {
                    "sql": "[polars] group_by=['a'] agg={'b': 'sum'}",
                    "columns": ["a", "b"],
                    "rows": [[1, 2], [3, 4]],
                    "row_count": 2,
                },
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        assert "x-result-truncated" not in response.headers

    async def test_export_csv_content(self, client, unique_email, db_session):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "[polars] group_by=[] agg={}",
                    "columns": ["a", "b"],
                    "rows": [[1, 2]],
                    "row_count": 1,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "csv"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        assert response.text.strip().splitlines() == ["a,b", "1,2"]

    async def test_export_specific_query_index(self, client, unique_email, db_session):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "[polars] group_by=[] agg={}",
                    "columns": ["a"],
                    "rows": [[1]],
                    "row_count": 1,
                },
                {
                    "sql": "[polars] group_by=[] agg={}",
                    "columns": ["a"],
                    "rows": [[2]],
                    "row_count": 1,
                },
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json", "query_index": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == [{"a": 1}]

    async def test_export_invalid_format_returns_422(self, client, unique_email, db_session):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [{"sql": "SELECT 1", "columns": ["a"], "rows": [[1]], "row_count": 1}],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "xml"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_export_without_results_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_export_out_of_range_query_index_returns_404(
        self, client, unique_email, db_session
    ):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [{"sql": "SELECT 1", "columns": ["a"], "rows": [[1]], "row_count": 1}],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"query_index": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_export_without_membership_returns_404(self, client, unique_email, db_session):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [{"sql": "SELECT 1", "columns": ["a"], "rows": [[1]], "row_count": 1}],
        )

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-export-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Export Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404

    async def test_export_real_sql_query_returns_full_result_beyond_evidence_cap(
        self, client, unique_email, db_session
    ):
        """RF-043: la evidencia persistida en Analysis.result_json esta
        acotada a 100 filas (tools.py::_EVIDENCE_ROW_CAP), pero el export
        de una consulta SQL real tiene que re-ejecutarla contra el
        dataset y devolver el resultado completo (150 filas aca), no la
        muestra acotada."""
        token, org_id, _dataset_id = await _register_and_import(client, unique_email)
        row_count = 150
        csv_content = b"n\n" + "\n".join(str(i) for i in range(row_count)).encode()
        dataset_id = await _import_csv(
            client, token, org_id, filename="big.csv", content=csv_content
        )
        table = await _qualified_table_name(db_session, dataset_id)

        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        # Simula lo que execute_readonly_sql hubiera persistido: solo una
        # MUESTRA de 100 filas como evidencia, aunque el resultado real
        # (row_count) tenga 150.
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": f"SELECT n FROM {table} ORDER BY n",
                    "columns": ["n"],
                    "rows": [[i] for i in range(100)],
                    "row_count": row_count,
                    "truncated": False,
                    "evidence_truncated": True,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == row_count
        assert body[0] == {"n": 0}
        assert body[-1] == {"n": row_count - 1}
        assert "x-result-truncated" not in response.headers

    async def test_export_polars_result_uses_persisted_evidence_unchanged(
        self, client, unique_email, db_session
    ):
        """RF-043: una entrada de run_analysis (prefijo "[polars]") no es
        SQL real, no se puede re-ejecutar - el export sigue sirviendo la
        evidencia persistida tal cual, sin tocar la base de datos."""
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "[polars] group_by=['a'] agg={'b': 'sum'}",
                    "columns": ["a", "b_sum"],
                    "rows": [[1, 2]],
                    "row_count": 1,
                    "truncated": False,
                    "evidence_truncated": False,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == [{"a": 1, "b_sum": 2}]
        assert "x-result-truncated" not in response.headers

    async def test_export_real_sql_query_truncated_by_max_rows_sets_header(
        self, client, unique_email, db_session, monkeypatch
    ):
        """RF-043: si la re-ejecucion contra Postgres sigue truncada (mas
        filas reales que agent_sql_max_rows), el header
        X-Result-Truncated tiene que comunicarlo - nunca meterlo adentro
        del archivo exportado."""
        monkeypatch.setattr(settings, "agent_sql_max_rows", 5)
        token, org_id, _dataset_id = await _register_and_import(client, unique_email)
        csv_content = b"n\n" + "\n".join(str(i) for i in range(10)).encode()
        dataset_id = await _import_csv(
            client, token, org_id, filename="trunc.csv", content=csv_content
        )
        table = await _qualified_table_name(db_session, dataset_id)

        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": f"SELECT n FROM {table} ORDER BY n",
                    "columns": ["n"],
                    "rows": [[i] for i in range(5)],
                    "row_count": 5,
                    "truncated": False,
                    "evidence_truncated": False,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 5
        assert response.headers["x-result-truncated"] == "true"

    async def test_export_polars_evidence_truncated_sets_header(
        self, client, unique_email, db_session
    ):
        """RF-043: una entrada [polars] cuya evidencia persistida ya venia
        acotada (evidence_truncated=true) tambien tiene que comunicar el
        truncamiento por header, aunque no haya re-ejecucion posible."""
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "[polars] group_by=['a'] agg={'b': 'sum'}",
                    "columns": ["a", "b_sum"],
                    "rows": [[1, 2]],
                    "row_count": 150,
                    "truncated": False,
                    "evidence_truncated": True,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers["x-result-truncated"] == "true"

    async def test_export_real_sql_query_execution_failure_returns_404(
        self, client, unique_email, db_session
    ):
        """RF-043: si la re-ejecucion contra Postgres falla (ej. la tabla
        fisica ya no existe), el endpoint responde 404 controlado - nunca
        un 500 crudo con detalles internos."""
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _set_result_directly(
            db_session,
            analysis_id,
            [
                {
                    "sql": "SELECT * FROM datasets.ds_does_not_exist_xyz",
                    "columns": ["a"],
                    "rows": [[1]],
                    "row_count": 1,
                    "truncated": False,
                    "evidence_truncated": False,
                }
            ],
        )

        response = await client.get(
            f"/api/analyses/{analysis_id}/export",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestListToolCalls:
    """RF-052: GET /api/analyses/tool-calls - vista agregada Owner/Admin
    de consultas y ejecuciones de agente de toda la organizacion."""

    async def test_owner_can_list_tool_calls_of_other_users_in_same_org(
        self, client, unique_email, db_session
    ):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        analyst_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"analyst-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Analyst Org",
            },
        )
        analyst_user_id = analyst_response.json()["user"]["id"]
        analyst_token = analyst_response.json()["access_token"]
        db_session.add(
            Membership(user_id=analyst_user_id, organization_id=org_id, role=Role.ANALYST)
        )
        await db_session.commit()

        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        analysis_id = create_response.json()["id"]
        tool_call_id = await _add_tool_call_directly(db_session, analysis_id)

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        entry = next(item for item in body if item["id"] == tool_call_id)
        assert entry["analysis_id"] == analysis_id
        assert entry["user_id"] == analyst_user_id
        assert entry["tool"] == "execute_readonly_sql"
        assert entry["status"] == "SUCCESS"

    async def test_analyst_cannot_list_tool_calls(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        analyst_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"analyst-403-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Analyst 403 Org",
            },
        )
        analyst_user_id = analyst_response.json()["user"]["id"]
        analyst_token = analyst_response.json()["access_token"]
        db_session.add(
            Membership(user_id=analyst_user_id, organization_id=org_id, role=Role.ANALYST)
        )
        await db_session.commit()

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert response.status_code == 403

    async def test_viewer_cannot_list_tool_calls(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        viewer_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"viewer-toolcalls-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Viewer ToolCalls Org",
            },
        )
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]
        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    async def test_owner_of_another_organization_cannot_see_this_orgs_tool_calls(
        self, client, unique_email, db_session
    ):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        await _add_tool_call_directly(db_session, analysis_id)

        outsider_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"outsider-toolcalls-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider ToolCalls Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 403

    async def test_list_tool_calls_without_token_is_rejected(self, client, unique_email):
        _token, org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.get(
            "/api/analyses/tool-calls", params={"organization_id": org_id}
        )
        assert response.status_code == 401

    async def test_raw_input_is_never_exposed_only_hash(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        sensitive_sql = "SELECT * FROM datasets.ds_x WHERE email = 'someone-sensitive@example.com'"
        await _add_tool_call_directly(
            db_session,
            analysis_id,
            input_json={"sql": sensitive_sql},
            input_hash="abc123hash",
        )

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        raw_text = response.text
        assert sensitive_sql not in raw_text
        assert "input_json" not in raw_text
        entry = response.json()[0]
        assert entry["input_hash"] == "abc123hash"

    async def test_pagination_limit_caps_results(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]
        for _ in range(3):
            await _add_tool_call_directly(db_session, analysis_id)

        response = await client.get(
            "/api/analyses/tool-calls",
            params={"organization_id": org_id, "limit": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2
