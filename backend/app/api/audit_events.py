import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_event import AuditEvent
from app.db.models.membership import Role
from app.db.models.user import User
from app.db.session import get_db
from app.domain.audit.schemas import AuditEventOut
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user

router = APIRouter(tags=["audit"])


@router.get("/audit-events", response_model=list[AuditEventOut])
async def list_audit_events(
    organization_id: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AuditEvent]:
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None or membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
    )
    return list(result.scalars())
