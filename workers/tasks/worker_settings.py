from arq.connections import RedisSettings

from app.core.config import settings
from tasks.example import noop


class WorkerSettings:
    """Configuración del worker ARQ.

    `functions` solo tiene el placeholder `noop` porque ARQ exige al menos
    una function registrada para poder arrancar (AssertionError si la lista
    está vacía). Los jobs reales (import de datasets, ejecución del agente)
    se agregan en Fase 1 en adelante — `noop` se retira en ese momento.
    """

    functions = [noop]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
