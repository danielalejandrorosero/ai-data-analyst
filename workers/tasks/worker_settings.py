from arq.connections import RedisSettings

from app.core.config import settings


class WorkerSettings:
    """Configuración del worker ARQ.

    `functions` queda vacío a propósito: los jobs reales (import de datasets,
    ejecución del agente) se agregan en Fase 1 en adelante, no en el
    scaffolding inicial.
    """

    functions: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
