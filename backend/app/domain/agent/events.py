import json
import uuid

from app.core.redis_client import redis_client


def _channel(analysis_id: uuid.UUID) -> str:
    return f"analysis:{analysis_id}:events"


async def publish_event(analysis_id: uuid.UUID, event: dict) -> None:
    """Progreso de una ejecucion (RF-022/CU-06) - el worker publica, la API
    (GET /analyses/{id}/events) retransmite por SSE. No falla el analysis
    si Redis esta caido (best-effort): el estado real siempre vive en
    Postgres, esto es solo la vista en vivo."""
    try:
        await redis_client.publish(_channel(analysis_id), json.dumps(event))
    except Exception:  # noqa: BLE001 - el progreso en vivo nunca puede tumbar el analysis
        pass
