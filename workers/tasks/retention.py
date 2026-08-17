import logging

from app.core.config import settings
from app.db.session import async_session_maker
from app.domain.retention.service import purge_old_analyses, purge_old_audit_events

logger = logging.getLogger("app.retention")


async def purge_old_data_job(ctx: dict) -> None:  # noqa: ARG001 - ctx lo exige ARQ
    """RF-053: cron job de mantenimiento (retencion configurable de logs y
    resultados). Se registra en `WorkerSettings.cron_jobs` (ver
    `worker_settings.py`) - no se dispara a mano ni desde un endpoint. Toda
    la logica de borrado vive en `domain/retention/service.py`; esta
    funcion solo resuelve la sesion, commitea y loguea.
    """
    async with async_session_maker() as db:
        deleted_audit_events = await purge_old_audit_events(
            db, older_than_days=settings.audit_event_retention_days
        )
        deleted_analyses = await purge_old_analyses(
            db, older_than_days=settings.analysis_retention_days
        )
        await db.commit()
    logger.info(
        "retention.purged audit_events=%s analyses=%s",
        deleted_audit_events,
        deleted_analyses,
    )
