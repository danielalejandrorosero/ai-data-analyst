import uuid

import pytest
from app.core.crypto import decrypt_secret
from app.db.models.data_source import DataSource
from sqlalchemy import select


@pytest.fixture
def _bypass_ssrf_guard(monkeypatch):
    """El guard SSRF (RF-010) bloquea legitimamente loopback/privado/
    link-local - pero en este entorno de test la unica Postgres real
    disponible para simular "una conexion externa" ES la Postgres de test
    (localhost). Estos tests no verifican el guard SSRF (eso tiene su
    propia clase, TestSsrfProtection, con IPs reales sin bypass) - aislan
    la logica de DSN/conexion/persistencia de la logica de SSRF."""
    import app.domain.datasets.connections as connections_module

    async def _noop(_host, _port):
        return None

    monkeypatch.setattr(connections_module, "_assert_host_is_not_internal", _noop)


async def _register_and_get_org(client, unique_email: str):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "correcthorsebattery",
            "organization_name": "Connections Test Org",
        },
    )
    body = register_response.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


class TestRegisterConnection:
    async def test_owner_can_register_a_valid_postgres_connection(
        self, client, unique_email, db_session, _bypass_ssrf_guard
    ):
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Test external DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["type"] == "postgres"
        assert body["host"] == "localhost"
        assert "password" not in body
        assert "secret_ref" not in body

        source = (
            await db_session.execute(
                select(DataSource).where(DataSource.id == uuid.UUID(body["id"]))
            )
        ).scalar_one()
        assert source.secret_ref is not None
        assert decrypt_secret(source.secret_ref) == "postgres"

    async def test_invalid_credentials_are_rejected_and_nothing_is_persisted(
        self, client, unique_email, db_session, _bypass_ssrf_guard
    ):
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Broken DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "definitely-wrong-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        count = (
            (
                await db_session.execute(
                    select(DataSource).where(
                        DataSource.organization_id == uuid.UUID(org_id),
                        DataSource.type == "postgres",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert count == []

    async def test_unreachable_host_is_rejected(self, client, unique_email):
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Unreachable DB",
                "host": "127.0.0.1",
                "port": 1,
                "database_name": "nope",
                "username": "nope",
                "password": "nope",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_viewer_cannot_register_connection(self, client, unique_email, db_session):
        from app.db.models.membership import Membership, Role

        token, org_id = await _register_and_get_org(client, unique_email)

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
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "x",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    async def test_analyst_cannot_register_connection(self, client, unique_email, db_session):
        from app.db.models.membership import Membership, Role

        token, org_id = await _register_and_get_org(client, unique_email)

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

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "x",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert response.status_code == 403

    async def test_registering_without_membership_returns_403(self, client, unique_email):
        _token, org_id = await _register_and_get_org(client, unique_email)

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
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "x",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 403

    async def test_registering_mysql_type_is_rejected_as_not_yet_supported(
        self, client, unique_email
    ):
        """MySQL esta explicitamente diferido (ver docs/SRS.md RF-010) -
        el schema Pydantic solo acepta Literal["postgres"], asi que un
        intento de "mysql" debe fallar la validacion del request, no
        llegar a intentar nada."""
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "mysql",
                "name": "x",
                "host": "localhost",
                "port": 3306,
                "database_name": "x",
                "username": "x",
                "password": "x",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestListConnections:
    async def test_returns_empty_list_when_no_connection_registered(self, client, unique_email):
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.get(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_the_registered_connection_without_secrets(
        self, client, unique_email, _bypass_ssrf_guard
    ):
        token, org_id = await _register_and_get_org(client, unique_email)

        register_response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Test external DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register_response.status_code == 201

        response = await client.get(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        connection = body[0]
        assert connection["type"] == "postgres"
        assert connection["name"] == "Test external DB"
        assert connection["host"] == "localhost"
        assert connection["port"] == 5432
        assert connection["database_name"] == "ai_data_analyst_test"
        assert connection["username"] == "postgres"
        assert connection["status"] == "active"
        assert "created_at" in connection
        assert "password" not in connection
        assert "secret_ref" not in connection

    async def test_viewer_can_list_connections(
        self, client, unique_email, db_session, _bypass_ssrf_guard
    ):
        from app.db.models.membership import Membership, Role

        token, org_id = await _register_and_get_org(client, unique_email)
        await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Test external DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

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

        response = await client.get(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_returns_401_without_token(self, client, unique_email):
        _token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.get(
            "/api/datasets/connections",
            params={"organization_id": org_id},
        )
        assert response.status_code == 401

    async def test_tenant_isolation_other_organizations_connection_is_not_listed(
        self, client, unique_email, _bypass_ssrf_guard
    ):
        token, org_id = await _register_and_get_org(client, unique_email)
        await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "Test external DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "ai_data_analyst_test",
                "username": "postgres",
                "password": "postgres",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        other_token, other_org_id = await _register_and_get_org(
            client, f"other-{unique_email}"
        )

        response = await client.get(
            "/api/datasets/connections",
            params={"organization_id": other_org_id},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestSsrfProtection:
    """Sin bypass del guard - estas prueban el guard SSRF de verdad, con
    IPs reales que no necesitan estar levantadas (se bloquean por rango
    antes de intentar ninguna conexion TCP)."""

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",  # loopback
            "10.0.0.5",  # RFC1918 privado
            "172.16.0.5",  # RFC1918 privado
            "192.168.1.5",  # RFC1918 privado
            "169.254.169.254",  # link-local / metadata de nube
        ],
    )
    async def test_internal_or_reserved_host_is_rejected(self, client, unique_email, host):
        token, org_id = await _register_and_get_org(client, unique_email)

        response = await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "SSRF probe",
                "host": host,
                "port": 5432,
                "database_name": "x",
                "username": "x",
                "password": "x",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_failed_attempt_is_audited(self, client, unique_email, db_session):
        from app.db.models.audit_event import AuditEvent

        token, org_id = await _register_and_get_org(client, unique_email)

        await client.post(
            "/api/datasets/connections",
            params={"organization_id": org_id},
            json={
                "type": "postgres",
                "name": "SSRF probe",
                "host": "127.0.0.1",
                "port": 5432,
                "database_name": "x",
                "username": "x",
                "password": "x",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        events = (
            (
                await db_session.execute(
                    select(AuditEvent).where(
                        AuditEvent.organization_id == uuid.UUID(org_id),
                        AuditEvent.action == "connection.test_failed",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert "127.0.0.1" in events[0].target
