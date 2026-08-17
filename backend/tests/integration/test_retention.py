import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from app.db.models.analysis import Analysis, AnalysisStatus
from app.db.models.audit_event import AuditEvent
from app.domain.retention.service import purge_old_analyses, purge_old_audit_events
from app.main import app as fastapi_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


@pytest_asyncio.fixture(scope="module")
async def _shared_context():
    """Registra un unico usuario/organizacion/dataset para todo el modulo,
    reusado por todos los tests de este archivo (via un AsyncClient propio,
    no el fixture `client` de conftest.py, que es function-scoped y no se
    puede inyectar en un fixture module-scoped). Evita chocar con el rate
    limit de `/api/auth/register` (`settings.rate_limit_auth`, "5/minute",
    ver `app/api/auth.py`/`app/core/rate_limit.py`) - un register por test
    en este archivo lo superaria facil. Solo lectura para las pruebas: no
    interactua con `_clean_retention_tables`, que solo borra `analyses`/
    `audit_events`, nunca `organizations`/`users`/`datasets`.
    """
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": f"retention-tests-{uuid.uuid4().hex[:12]}@example.com",
                "password": "correcthorsebattery",
                "organization_name": "Retention Test Org",
            },
        )
        body = register_response.json()
        org_id = uuid.UUID(body["user"]["memberships"][0]["organization_id"])
        user_id = uuid.UUID(body["user"]["id"])
        token = body["access_token"]

        import_response = await client.post(
            "/api/datasets/import",
            data={"organization_id": str(org_id)},
            files={
                "file": (
                    "dataset.csv",
                    io.BytesIO(b"product,units\nWidget A,10\nWidget B,5\n"),
                    "text/csv",
                )
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        dataset_id = uuid.UUID(import_response.json()["id"])

    return org_id, user_id, dataset_id


@pytest_asyncio.fixture(autouse=True)
async def _clean_retention_tables(db_session):
    """Aisla cada test de este archivo entre si: `purge_old_analyses`/
    `purge_old_audit_events` corren a nivel de plataforma (sin
    organization_id), asi que filas viejas dejadas por un test anterior
    contaminarian el conteo `deleted` de otro test que use un cutoff laxo.
    `db_session` no hace rollback automatico entre tests (ver conftest.py -
    un solo `_prepare_database` por sesion)."""
    await db_session.execute(delete(Analysis))
    await db_session.execute(delete(AuditEvent))
    await db_session.commit()
    yield


def _old_date() -> datetime:
    return datetime.now(UTC) - timedelta(days=365)


def _recent_date() -> datetime:
    return datetime.now(UTC) - timedelta(days=1)


class TestPurgeOldAuditEvents:
    async def test_only_deletes_events_older_than_threshold(self, db_session, _shared_context):
        org_id, user_id, _dataset_id = _shared_context

        old_event = AuditEvent(
            organization_id=org_id,
            actor_id=user_id,
            action="login",
            created_at=_old_date(),
        )
        recent_event = AuditEvent(
            organization_id=org_id,
            actor_id=user_id,
            action="login",
            created_at=_recent_date(),
        )
        db_session.add_all([old_event, recent_event])
        await db_session.commit()

        deleted = await purge_old_audit_events(db_session, older_than_days=90)
        await db_session.commit()

        assert deleted == 1
        remaining_ids = (await db_session.execute(select(AuditEvent.id))).scalars().all()
        assert old_event.id not in remaining_ids
        assert recent_event.id in remaining_ids

    async def test_disabled_retention_deletes_nothing(self, db_session, _shared_context):
        org_id, user_id, _dataset_id = _shared_context

        old_event = AuditEvent(
            organization_id=org_id,
            actor_id=user_id,
            action="login",
            created_at=_old_date(),
        )
        db_session.add(old_event)
        await db_session.commit()

        for older_than_days in (0, -1):
            deleted = await purge_old_audit_events(db_session, older_than_days=older_than_days)
            await db_session.commit()
            assert deleted == 0

        remaining_ids = (await db_session.execute(select(AuditEvent.id))).scalars().all()
        assert old_event.id in remaining_ids


class TestPurgeOldAnalyses:
    async def test_only_deletes_terminal_analyses_older_than_threshold(
        self, db_session, _shared_context
    ):
        org_id, user_id, dataset_id = _shared_context

        old_completed = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Vieja completada",
            status=AnalysisStatus.COMPLETED,
            created_at=_old_date(),
        )
        recent_completed = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Reciente completada",
            status=AnalysisStatus.COMPLETED,
            created_at=_recent_date(),
        )
        old_queued = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Vieja pero en curso",
            status=AnalysisStatus.QUEUED,
            created_at=_old_date(),
        )
        db_session.add_all([old_completed, recent_completed, old_queued])
        await db_session.commit()

        deleted = await purge_old_analyses(db_session, older_than_days=180)
        await db_session.commit()

        assert deleted == 1
        remaining_ids = (await db_session.execute(select(Analysis.id))).scalars().all()
        assert old_completed.id not in remaining_ids
        assert recent_completed.id in remaining_ids
        assert old_queued.id in remaining_ids

    async def test_non_terminal_analysis_never_deleted_even_if_old(
        self, db_session, _shared_context
    ):
        org_id, user_id, dataset_id = _shared_context

        old_queued = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Vieja pero en curso",
            status=AnalysisStatus.QUEUED,
            created_at=_old_date(),
        )
        db_session.add(old_queued)
        await db_session.commit()

        deleted = await purge_old_analyses(db_session, older_than_days=1)
        await db_session.commit()

        assert deleted == 0
        remaining_ids = (await db_session.execute(select(Analysis.id))).scalars().all()
        assert old_queued.id in remaining_ids

    async def test_disabled_retention_deletes_nothing(self, db_session, _shared_context):
        org_id, user_id, dataset_id = _shared_context

        old_completed = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Vieja completada",
            status=AnalysisStatus.COMPLETED,
            created_at=_old_date(),
        )
        db_session.add(old_completed)
        await db_session.commit()

        for older_than_days in (0, -1):
            deleted = await purge_old_analyses(db_session, older_than_days=older_than_days)
            await db_session.commit()
            assert deleted == 0

        remaining_ids = (await db_session.execute(select(Analysis.id))).scalars().all()
        assert old_completed.id in remaining_ids

    async def test_cascade_deletes_agent_runs_tool_calls_and_artifacts(
        self, db_session, _shared_context
    ):
        from app.db.models.agent_run import AgentRun, AgentRunStatus
        from app.db.models.analysis_artifact import AnalysisArtifact, ArtifactType
        from app.db.models.tool_call import ToolCall, ToolCallStatus

        org_id, user_id, dataset_id = _shared_context

        old_completed = Analysis(
            organization_id=org_id,
            user_id=user_id,
            dataset_id=dataset_id,
            question="Vieja completada con hijos",
            status=AnalysisStatus.COMPLETED,
            created_at=_old_date(),
        )
        db_session.add(old_completed)
        await db_session.flush()

        agent_run = AgentRun(
            analysis_id=old_completed.id,
            model="test-model",
            status=AgentRunStatus.COMPLETED,
            trace_id="trace-retention-test",
        )
        db_session.add(agent_run)
        await db_session.flush()

        tool_call = ToolCall(
            agent_run_id=agent_run.id,
            tool="inspect_schema",
            input_json={},
            input_hash="deadbeef",
            status=ToolCallStatus.SUCCESS,
            duration_ms=1,
        )
        artifact = AnalysisArtifact(
            analysis_id=old_completed.id,
            type=ArtifactType.CHART,
            spec_json={"type": "bar"},
            source_sql="SELECT 1",
        )
        db_session.add_all([tool_call, artifact])
        await db_session.commit()

        deleted = await purge_old_analyses(db_session, older_than_days=180)
        await db_session.commit()

        assert deleted == 1
        assert (
            await db_session.execute(select(AgentRun).where(AgentRun.id == agent_run.id))
        ).scalar_one_or_none() is None
        assert (
            await db_session.execute(select(ToolCall).where(ToolCall.id == tool_call.id))
        ).scalar_one_or_none() is None
        assert (
            await db_session.execute(
                select(AnalysisArtifact).where(AnalysisArtifact.id == artifact.id)
            )
        ).scalar_one_or_none() is None
