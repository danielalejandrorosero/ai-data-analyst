import os
import uuid

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_data_analyst_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["SECRET_ENCRYPTION_KEY"] = "test-encryption-key-not-for-production"
os.environ["AGENT_DATABASE_URL"] = (
    "postgresql+asyncpg://agent_readonly:changeme_agent_readonly@localhost:5432/ai_data_analyst_test"
)
# Los tests nunca deben depender de si el .env real del desarrollador tiene
# una LLM_API_KEY configurada o no - se fuerzan vacias explicitamente para
# que build_agent() falle de forma deterministica en el path que lo espera
# (test_missing_llm_config_leaves_analysis_failed_not_500), sin importar el
# entorno local.
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_MODEL"] = ""
# La suite entera corre cientos de requests seguidos de login/register/import
# en la misma sesion (misma IP simulada de httpx, y unique_email no cambia
# eso) - con el rate limiter prendido se pisarian entre si y romperian tests
# que no tienen nada que ver con rate limiting. Se apaga por default aca y
# se prende puntualmente (monkeypatch sobre app.core.rate_limit.limiter.enabled)
# en los tests dedicados a probar el 429 (tests/integration/test_rate_limit.py).
os.environ["RATE_LIMIT_ENABLED"] = "false"

import app.db.models  # noqa: F401 - registra los modelos en Base.metadata
import pytest
import pytest_asyncio
import sqlalchemy as sa
from app.core.config import settings
from app.db.base import Base
from app.db.session import async_session_maker
from app.main import app as fastapi_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        # Fase 6 (document_chunks.embedding es vector(384)): la extension
        # tiene que existir ANTES de create_all - en la DB real la crea la
        # migracion c07af8be762c, aca no corre Alembic.
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        # El schema "datasets" (tablas fisicas dinamicas de datasets
        # importados) no vive en Base.metadata - se limpia aparte.
        await conn.execute(sa.text("DROP SCHEMA IF EXISTS datasets CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # El schema "datasets" recien se crea de nuevo cuando el primer
        # test importa un dataset (CreateSchema if_not_exists en
        # domain/datasets/service.py) - pero eso NO reaplica USAGE sobre
        # el schema (fue parte del schema que se acaba de dropear arriba).
        # A proposito NO se reotorga GRANT SELECT ON ALL TABLES ni
        # ALTER DEFAULT PRIVILEGES aca (mismo criterio que
        # infrastructure/postgres/init/002-agent-readonly-role.sh,
        # docs/security/threat-model.md "Aislamiento de tenant en el
        # schema datasets es de una sola capa") - el SELECT explicito por
        # tabla lo otorga domain/datasets/service.py::_grant_agent_readonly_select
        # en import_file/reimport_file, y los tests de integracion pasan
        # por ese mismo codigo real, no por un atajo del fixture.
        await conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS datasets"))
        await conn.execute(sa.text("GRANT USAGE ON SCHEMA datasets TO agent_readonly"))
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"
