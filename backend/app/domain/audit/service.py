import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_event import AuditEvent


async def record_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    target: str | None = None,
) -> AuditEvent:
    """Registra un evento de auditoría (RF-004, RF-052).

    No hace commit — queda a cargo del caller, para que el evento se
    confirme en la misma transacción que la operación que audita.
    """
    event = AuditEvent(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        target=target,
    )
    db.add(event)
    await db.flush()
    return event
