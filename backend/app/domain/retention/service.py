"""RF-053: retencion configurable de logs y resultados.

Job de mantenimiento a nivel de toda la plataforma - a proposito NO filtra
por `organization_id` (no es una operacion de usuario/tenant, ver
`.claude/rules/database.md`). Invocado desde `workers/tasks/retention.py`
como cron job de ARQ, nunca a mano desde un endpoint.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.analysis import TERMINAL_ANALYSIS_STATUSES, Analysis
from app.db.models.audit_event import AuditEvent


async def purge_old_audit_events(db: AsyncSession, *, older_than_days: int) -> int:
    """Borra `audit_events` con `created_at` mas viejo que `older_than_days`.

    `older_than_days <= 0` significa retencion deshabilitada: no se borra
    nada (ver comentario en `app/core/config.py`). No hace commit, queda a
    cargo del caller.
    """
    if older_than_days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    return result.rowcount or 0


async def purge_old_analyses(db: AsyncSession, *, older_than_days: int) -> int:
    """Borra `analyses` con `created_at` mas viejo que `older_than_days`,
    SOLO si estan en un estado terminal (`TERMINAL_ANALYSIS_STATUSES`) - un
    analysis en curso nunca se borra sin importar su antiguedad, borrarlo
    dejaria un job de ARQ corriendo apuntando a una fila inexistente.

    `agent_runs`/`tool_calls`/`analysis_artifacts` caen solos via
    `ON DELETE CASCADE` (FK real en DB, ver `.claude/rules/database.md`) -
    no hace falta borrarlos a mano aca.

    `older_than_days <= 0` significa retencion deshabilitada: no se borra
    nada. No hace commit, queda a cargo del caller.
    """
    if older_than_days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await db.execute(
        delete(Analysis).where(
            Analysis.created_at < cutoff,
            Analysis.status.in_(TERMINAL_ANALYSIS_STATUSES),
        )
    )
    return result.rowcount or 0
