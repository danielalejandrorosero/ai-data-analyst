import os
import uuid

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_data_analyst_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["SECRET_ENCRYPTION_KEY"] = "test-encryption-key-not-for-production"

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
        # El schema "datasets" (tablas fisicas dinamicas de datasets
        # importados) no vive en Base.metadata - se limpia aparte.
        await conn.execute(sa.text("DROP SCHEMA IF EXISTS datasets CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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
