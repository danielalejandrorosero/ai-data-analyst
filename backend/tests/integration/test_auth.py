async def _register(
    client, email: str, password: str = "correcthorsebattery", org: str = "Test Org"
):
    return await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "organization_name": org},
    )


class TestRegister:
    async def test_register_creates_user_org_and_owner_membership(self, client, unique_email):
        response = await _register(client, unique_email)

        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == unique_email
        assert len(body["user"]["memberships"]) == 1
        assert body["user"]["memberships"][0]["role"] == "OWNER"
        assert body["access_token"]

    async def test_register_duplicate_email_is_rejected(self, client, unique_email):
        first = await _register(client, unique_email)
        assert first.status_code == 201

        second = await _register(client, unique_email)
        assert second.status_code == 409

    async def test_register_rejects_short_password(self, client, unique_email):
        response = await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": "short", "organization_name": "Org"},
        )
        assert response.status_code == 422


class TestLogin:
    async def test_login_with_correct_credentials_returns_token(self, client, unique_email):
        await _register(client, unique_email, password="correcthorsebattery")

        response = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "correcthorsebattery"},
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_login_with_wrong_password_is_rejected(self, client, unique_email):
        await _register(client, unique_email, password="correcthorsebattery")

        response = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_with_wrong_password_audits_the_failed_attempt(self, client, unique_email):
        register_response = await _register(client, unique_email, password="correcthorsebattery")
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "wrongpassword"},
        )

        response = await client.get(
            f"/api/audit-events?organization_id={org_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        actions = {event["action"] for event in response.json()}
        assert "auth.login_failed" in actions

    async def test_login_with_unknown_email_is_rejected(self, client):
        response = await client.post(
            "/api/auth/login",
            json={"email": "no-existe@example.com", "password": "whatever123"},
        )
        assert response.status_code == 401


class TestMe:
    async def test_me_without_token_is_rejected(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_me_with_invalid_token_is_rejected(self, client):
        response = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401

    async def test_me_with_valid_token_returns_user(self, client, unique_email):
        register_response = await _register(client, unique_email)
        token = register_response.json()["access_token"]

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == unique_email


class TestChangePassword:
    async def test_change_password_allows_login_with_new_password_and_not_old(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email, password="correcthorsebattery")
        token = register_response.json()["access_token"]

        response = await client.patch(
            "/api/auth/me/password",
            json={"current_password": "correcthorsebattery", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        new_login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "newpassword123"},
        )
        assert new_login.status_code == 200

        old_login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "correcthorsebattery"},
        )
        assert old_login.status_code == 401

    async def test_change_password_with_wrong_current_password_is_rejected(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email, password="correcthorsebattery")
        token = register_response.json()["access_token"]

        response = await client.patch(
            "/api/auth/me/password",
            json={"current_password": "wrongpassword", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (400, 401)

        still_old = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "correcthorsebattery"},
        )
        assert still_old.status_code == 200

    async def test_change_password_without_token_is_rejected(self, client):
        response = await client.patch(
            "/api/auth/me/password",
            json={"current_password": "whatever123", "new_password": "newpassword123"},
        )
        assert response.status_code == 401

    async def test_change_password_with_short_new_password_is_rejected(self, client, unique_email):
        register_response = await _register(client, unique_email, password="correcthorsebattery")
        token = register_response.json()["access_token"]

        response = await client.patch(
            "/api/auth/me/password",
            json={"current_password": "correcthorsebattery", "new_password": "short"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestOrganizations:
    async def test_authenticated_user_can_create_additional_organization(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email)
        token = register_response.json()["access_token"]

        response = await client.post(
            "/api/organizations",
            json={"name": "Segunda Org"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["role"] == "OWNER"

    async def test_create_organization_without_token_is_rejected(self, client):
        response = await client.post("/api/organizations", json={"name": "X"})
        assert response.status_code == 401


class TestAuditEventsRbacAndTenantIsolation:
    async def test_owner_can_list_own_org_audit_events(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        response = await client.get(
            f"/api/audit-events?organization_id={org_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        actions = {event["action"] for event in response.json()}
        assert "auth.register" in actions

    async def test_user_cannot_see_audit_events_of_another_organization(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        org_id = owner_response.json()["user"]["memberships"][0]["organization_id"]

        other_email = f"other-{unique_email}"
        other_response = await _register(client, other_email)
        other_token = other_response.json()["access_token"]

        response = await client.get(
            f"/api/audit-events?organization_id={org_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 403

    async def test_audit_events_without_token_is_rejected(self, client, unique_email):
        register_response = await _register(client, unique_email)
        org_id = register_response.json()["user"]["memberships"][0]["organization_id"]

        response = await client.get(f"/api/audit-events?organization_id={org_id}")
        assert response.status_code == 401
