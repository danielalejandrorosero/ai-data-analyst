from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import settings

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    """Pool lazy compartido para encolar jobs (RF-025, Fase 4) - un solo
    pool por proceso de la API, no uno por request."""
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool
