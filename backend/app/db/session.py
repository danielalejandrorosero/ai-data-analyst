from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# RNF-004: pool_size/max_overflow default de SQLAlchemy (5+10=15) se queda
# corto frente a worker_settings.max_jobs=25 (workers/tasks/worker_settings.py)
# - cada job del worker toma una conexion de este engine via get_db() (breve,
# por operacion - no la mantiene abierta toda la corrida). Este mismo modulo
# lo importan tanto la API (multiplicado por --workers de uvicorn, ver
# infrastructure/docker/backend.Dockerfile) como el worker de ARQ, cada
# proceso con su propio pool - el total se calculo contra
# max_connections=100 de Postgres (confirmado con `SHOW max_connections`)
# dejando margen para pgadmin/tests.
engine = create_async_engine(
    settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
