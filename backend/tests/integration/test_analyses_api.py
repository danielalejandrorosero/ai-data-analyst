import io
import uuid

import pytest
from app.db.models.membership import Membership, Role


@pytest.fixture(autouse=True)
def _stub_run_analysis(monkeypatch):
    """Los tests de este archivo verifican el endpoint HTTP (RBAC, 404,
    forma de la respuesta) - la orquestacion real del agente ya tiene su
    propia cobertura en test_agent_orchestrator.py contra la capa de
    servicio directamente. Mockear evita que el endpoint intente llamar a
    un LLM real (no hay LLM_API_KEY en el entorno de test)."""
    import app.api.v1.analyses as analyses_module
    from app.db.models.analysis import AnalysisStatus

    async def fake_run_analysis(db, *, analysis, dataset, agent=None):  # noqa: ARG001
        analysis.status = AnalysisStatus.COMPLETED
        analysis.answer = "Respuesta simulada para test"
        analysis.result_json = {"sql": "SELECT 1", "columns": [], "rows": [], "row_count": 0}
        await db.commit()

    monkeypatch.setattr(analyses_module, "run_analysis", fake_run_analysis)


async def _register_and_import(client, unique_email: str):
    register_response = await client.post(
        "/api/v1/auth/register",
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
        "/api/v1/datasets/import",
        data={"organization_id": org_id},
        files={"file": ("d.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = import_response.json()["id"]
    return token, org_id, dataset_id


class TestCreateAnalysis:
    async def test_analyst_can_create_analysis(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "Cuantas filas hay?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["answer"] == "Respuesta simulada para test"

    async def test_create_analysis_without_token_is_rejected(self, client, unique_email):
        _token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/v1/analyses", json={"dataset_id": dataset_id, "question": "x"}
        )
        assert response.status_code == 401

    async def test_create_analysis_for_unknown_dataset_returns_404(self, client, unique_email):
        token, _org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": str(uuid.uuid4()), "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_create_analysis_for_dataset_without_membership_returns_404(
        self, client, unique_email
    ):
        _token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        outsider_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"outsider-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Outsider Org",
            },
        )
        outsider_token = outsider_response.json()["access_token"]

        response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 404

    async def test_viewer_cannot_create_analysis(self, client, unique_email, db_session):
        token, org_id, dataset_id = await _register_and_import(client, unique_email)

        viewer_response = await client.post(
            "/api/v1/auth/register",
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
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403


class TestGetAnalysis:
    async def test_owner_can_fetch_their_analysis(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)

        create_response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/analyses/{analysis_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["id"] == analysis_id

    async def test_get_analysis_without_token_is_rejected(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        response = await client.get(f"/api/v1/analyses/{analysis_id}")
        assert response.status_code == 401

    async def test_get_analysis_of_another_organization_returns_404(self, client, unique_email):
        token, _org_id, dataset_id = await _register_and_import(client, unique_email)
        create_response = await client.post(
            "/api/v1/analyses",
            json={"dataset_id": dataset_id, "question": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = create_response.json()["id"]

        other_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"other-{unique_email}",
                "password": "correcthorsebattery",
                "organization_name": "Other Org",
            },
        )
        other_token = other_response.json()["access_token"]

        response = await client.get(
            f"/api/v1/analyses/{analysis_id}", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert response.status_code == 404

    async def test_get_unknown_analysis_returns_404(self, client, unique_email):
        token, _org_id, _dataset_id = await _register_and_import(client, unique_email)

        response = await client.get(
            f"/api/v1/analyses/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
