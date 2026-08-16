import io
import uuid

import pytest
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.membership import Membership, Role
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


async def _set_status_directly(db_session, analysis_id: str, status: AnalysisStatus) -> None:
    """Simula que el worker (nunca corre de verdad en estos tests, ver
    _stub_arq) ya termino de procesar el job."""
    analysis = (
        await db_session.execute(select(Analysis).where(Analysis.id == uuid.UUID(analysis_id)))
    ).scalar_one()
    analysis.status = status
    await db_session.commit()


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
        db_session.add(
            Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER)
        )
        await db_session.commit()

        response = await client.get(
            "/api/analyses",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_listing_analyses_of_another_organization_returns_403(
        self, client, unique_email
    ):
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
