import hashlib
import io

import pytest
from app.core.rate_limit import limiter
from app.domain.documents import embeddings as embeddings_module


def _fake_vector(text: str) -> list[float]:
    """Determinista y barato - mismo patron que test_documents.py, evita
    descargar/correr el modelo real de embeddings solo para probar que
    GET /documents/search rate-limitea."""
    digest = hashlib.sha256(text.encode()).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(384)]


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings_module, "embed_query", lambda q: _fake_vector(q))


@pytest.fixture(autouse=True)
def _enable_rate_limiting(monkeypatch):
    """conftest.py apaga el rate limiter globalmente (RATE_LIMIT_ENABLED=false)
    para que el resto de la suite no se pise entre tests. Solo este modulo lo
    prende, y limpia el storage de Redis antes/despues de cada test para que
    los tests de este mismo archivo no se contaminen entre si (todos comparten
    la misma IP simulada de httpx para login/register)."""
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    yield
    limiter.reset()


async def _register(
    client, email: str, password: str = "correcthorsebattery", org: str = "RateLimit Org"
):
    return await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "organization_name": org},
    )


def _csv_file(content: str = "product,units\nWidget A,10\nWidget B,5\n"):
    return {"file": ("dataset.csv", io.BytesIO(content.encode()), "text/csv")}


def _txt_file(content: str = "El margen bruto objetivo de la compania es 35%."):
    return {"file": ("politicas.txt", io.BytesIO(content.encode()), "text/plain")}


class TestLoginRateLimit:
    async def test_login_returns_429_after_exceeding_the_per_ip_limit(self, client, unique_email):
        await _register(client, unique_email)

        # settings.rate_limit_auth default es "5/minute" - las primeras 5
        # cuentan contra el limite (aca con credenciales incorrectas
        # a proposito, para no depender de que login exitoso tambien
        # cuente - de hecho slowapi cuenta el hit ANTES de ejecutar el
        # body, asi que cualquier resultado de negocio cuenta igual).
        for _ in range(5):
            response = await client.post(
                "/api/auth/login",
                json={"email": unique_email, "password": "wrongpassword"},
            )
            assert response.status_code == 401

        response = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "wrongpassword"},
        )
        assert response.status_code == 429


class TestRegisterRateLimit:
    async def test_register_returns_429_after_exceeding_the_per_ip_limit(
        self, client, unique_email
    ):
        for i in range(5):
            response = await _register(client, f"{i}-{unique_email}")
            assert response.status_code == 201

        response = await _register(client, f"extra-{unique_email}")
        assert response.status_code == 429


class TestDatasetImportRateLimit:
    async def test_import_returns_429_after_exceeding_the_per_user_limit(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        org_id = body["user"]["memberships"][0]["organization_id"]

        # settings.rate_limit_expensive default es "10/minute".
        for _ in range(10):
            response = await client.post(
                "/api/datasets/import",
                data={"organization_id": org_id},
                files=_csv_file(),
                headers=headers,
            )
            assert response.status_code == 201

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers=headers,
        )
        assert response.status_code == 429

    async def test_import_rate_limit_is_scoped_per_user_not_shared(self, client, unique_email):
        """Dos usuarios distintos no comparten contador (key_by_user, no
        get_remote_address) - si el usuario A agota su limite, el usuario B
        todavia puede importar."""
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_headers = {"Authorization": f"Bearer {owner_body['access_token']}"}
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        for _ in range(10):
            response = await client.post(
                "/api/datasets/import",
                data={"organization_id": owner_org_id},
                files=_csv_file(),
                headers=owner_headers,
            )
            assert response.status_code == 201

        blocked = await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id},
            files=_csv_file(),
            headers=owner_headers,
        )
        assert blocked.status_code == 429

        other_response = await _register(client, f"other-{unique_email}")
        other_body = other_response.json()
        other_headers = {"Authorization": f"Bearer {other_body['access_token']}"}
        other_org_id = other_body["user"]["memberships"][0]["organization_id"]

        allowed = await client.post(
            "/api/datasets/import",
            data={"organization_id": other_org_id},
            files=_csv_file(),
            headers=other_headers,
        )
        assert allowed.status_code == 201


class TestDocumentUploadRateLimit:
    async def test_upload_returns_429_after_exceeding_the_per_user_limit(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        org_id = body["user"]["memberships"][0]["organization_id"]

        for _ in range(10):
            response = await client.post(
                "/api/documents",
                data={"organization_id": org_id},
                files=_txt_file(),
                headers=headers,
            )
            assert response.status_code == 202

        response = await client.post(
            "/api/documents",
            data={"organization_id": org_id},
            files=_txt_file(),
            headers=headers,
        )
        assert response.status_code == 429


class TestDocumentSearchRateLimit:
    async def test_search_returns_429_after_exceeding_the_per_user_limit(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        org_id = body["user"]["memberships"][0]["organization_id"]

        for _ in range(10):
            response = await client.get(
                f"/api/documents/search?organization_id={org_id}&q=margen",
                headers=headers,
            )
            assert response.status_code == 200

        response = await client.get(
            f"/api/documents/search?organization_id={org_id}&q=margen",
            headers=headers,
        )
        assert response.status_code == 429
