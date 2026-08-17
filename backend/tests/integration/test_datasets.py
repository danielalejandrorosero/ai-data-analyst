import io

from app.db.models.membership import Membership, Role


async def _register(
    client, email: str, password: str = "correcthorsebattery", org: str = "Test Org"
):
    return await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "organization_name": org},
    )


def _csv_file(content: str = "product,units\nWidget A,10\nWidget B,5\n"):
    return {"file": ("dataset.csv", io.BytesIO(content.encode()), "text/csv")}


class TestImportDataset:
    async def test_owner_can_import_csv_and_it_lands_in_a_real_table(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id, "name": "Ventas"},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        result = response.json()
        assert result["row_count"] == 2
        assert result["name"] == "Ventas"
        columns_by_name = {c["name"]: c["type"] for c in result["columns"]}
        assert columns_by_name["product"] == "string"
        assert columns_by_name["units"] == "integer"

    async def test_import_without_token_is_rejected(self, client, unique_email):
        register_response = await _register(client, unique_email)
        org_id = register_response.json()["user"]["memberships"][0]["organization_id"]

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
        )
        assert response.status_code == 401

    async def test_import_rejects_unsupported_extension(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files={
                "file": ("dataset.exe", io.BytesIO(b"not a dataset"), "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_import_rejects_garbage_csv_content(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files={"file": ("dataset.csv", io.BytesIO(b"\x00\x01\x02binary garbage"), "text/csv")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_viewer_cannot_import_dataset(self, client, unique_email, db_session):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        org_id = body["user"]["memberships"][0]["organization_id"]

        viewer_email = f"viewer-{unique_email}"
        viewer_response = await _register(client, viewer_email, org="Viewer Org")
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]

        # Convertimos al viewer en miembro VIEWER de la organizacion del owner,
        # directamente en la DB (todavia no existe endpoint de invitaciones).
        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    async def test_import_to_organization_without_membership_is_rejected(
        self, client, unique_email
    ):
        owner_response = await _register(client, unique_email)
        org_id = owner_response.json()["user"]["memberships"][0]["organization_id"]

        # Usuario autenticado, pero sin ningun membership en `org_id`
        # (ni siquiera VIEWER) - distinto del caso VIEWER de arriba.
        outsider_response = await _register(client, f"outsider-{unique_email}")
        outsider_token = outsider_response.json()["access_token"]

        response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 403


class TestListAndSchema:
    async def test_list_includes_source_type_extension_and_column_count(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_token = owner_body["access_token"]
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id, "name": "Ventas"},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = await client.get(
            f"/api/datasets?organization_id={owner_org_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        [dataset] = response.json()
        assert dataset["source_type"] == "upload"
        assert dataset["source_extension"] == "csv"
        assert dataset["column_count"] == 2

    async def test_list_only_returns_datasets_of_that_organization(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_token = owner_body["access_token"]
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        other_response = await _register(client, f"other-{unique_email}")
        other_body = other_response.json()
        other_token = other_body["access_token"]
        other_org_id = other_body["user"]["memberships"][0]["organization_id"]

        response = await client.get(
            f"/api/datasets?organization_id={other_org_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_datasets_without_token_is_rejected(self, client, unique_email):
        register_response = await _register(client, unique_email)
        org_id = register_response.json()["user"]["memberships"][0]["organization_id"]

        response = await client.get(f"/api/datasets?organization_id={org_id}")
        assert response.status_code == 401

    async def test_list_datasets_without_membership_is_rejected(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_org_id = owner_response.json()["user"]["memberships"][0]["organization_id"]

        outsider_response = await _register(client, f"outsider-{unique_email}")
        outsider_token = outsider_response.json()["access_token"]

        response = await client.get(
            f"/api/datasets?organization_id={owner_org_id}",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert response.status_code == 403

    async def test_get_schema_without_token_is_rejected(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_token = owner_body["access_token"]
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        dataset_id = import_response.json()["id"]

        response = await client.get(f"/api/datasets/{dataset_id}/schema")
        assert response.status_code == 401

    async def test_get_schema_of_dataset_in_another_org_returns_404(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_token = owner_body["access_token"]
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        dataset_id = import_response.json()["id"]

        other_response = await _register(client, f"other-{unique_email}")
        other_token = other_response.json()["access_token"]

        response = await client.get(
            f"/api/datasets/{dataset_id}/schema",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 404


class TestUpdateDatasetAnnotations:
    async def test_owner_can_annotate_dataset_and_specific_columns(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id, "name": "Ventas"},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {token}"},
        )
        dataset_id = import_response.json()["id"]

        response = await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={
                "description": "Ventas mensuales por producto",
                "column_descriptions": {"units": "Unidades vendidas en el periodo"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["description"] == "Ventas mensuales por producto"

        schema_response = await client.get(
            f"/api/datasets/{dataset_id}/schema",
            headers={"Authorization": f"Bearer {token}"},
        )
        schema = schema_response.json()
        assert schema["description"] == "Ventas mensuales por producto"
        columns_by_name = {c["name"]: c.get("description") for c in schema["columns"]}
        assert columns_by_name["units"] == "Unidades vendidas en el periodo"
        # La columna "product" no vino en column_descriptions - no se toca.
        assert columns_by_name["product"] is None

    async def test_partial_update_does_not_overwrite_other_column_descriptions(
        self, client, unique_email
    ):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {token}"},
        )
        dataset_id = import_response.json()["id"]

        await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={"column_descriptions": {"product": "Nombre del producto"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={"column_descriptions": {"units": "Unidades vendidas"}},
            headers={"Authorization": f"Bearer {token}"},
        )

        schema_response = await client.get(
            f"/api/datasets/{dataset_id}/schema",
            headers={"Authorization": f"Bearer {token}"},
        )
        columns_by_name = {
            c["name"]: c.get("description") for c in schema_response.json()["columns"]
        }
        assert columns_by_name["product"] == "Nombre del producto"
        assert columns_by_name["units"] == "Unidades vendidas"

    async def test_nonexistent_column_in_payload_is_ignored(self, client, unique_email):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        token = body["access_token"]
        org_id = body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {token}"},
        )
        dataset_id = import_response.json()["id"]

        response = await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={"column_descriptions": {"columna_que_no_existe": "algo"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        schema_response = await client.get(
            f"/api/datasets/{dataset_id}/schema",
            headers={"Authorization": f"Bearer {token}"},
        )
        columns_by_name = {
            c["name"]: c.get("description") for c in schema_response.json()["columns"]
        }
        assert columns_by_name == {"product": None, "units": None}

    async def test_viewer_cannot_annotate_dataset(self, client, unique_email, db_session):
        register_response = await _register(client, unique_email)
        body = register_response.json()
        org_id = body["user"]["memberships"][0]["organization_id"]
        owner_token = body["access_token"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        dataset_id = import_response.json()["id"]

        viewer_email = f"viewer-{unique_email}"
        viewer_response = await _register(client, viewer_email, org="Viewer Org")
        viewer_user_id = viewer_response.json()["user"]["id"]
        viewer_token = viewer_response.json()["access_token"]

        db_session.add(Membership(user_id=viewer_user_id, organization_id=org_id, role=Role.VIEWER))
        await db_session.commit()

        response = await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={"description": "no deberia poder"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    async def test_annotate_dataset_in_another_org_returns_404(self, client, unique_email):
        owner_response = await _register(client, unique_email)
        owner_body = owner_response.json()
        owner_token = owner_body["access_token"]
        owner_org_id = owner_body["user"]["memberships"][0]["organization_id"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": owner_org_id},
            files=_csv_file(),
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        dataset_id = import_response.json()["id"]

        other_response = await _register(client, f"other-{unique_email}")
        other_token = other_response.json()["access_token"]

        response = await client.patch(
            f"/api/datasets/{dataset_id}/annotations",
            json={"description": "no deberia poder"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 404
