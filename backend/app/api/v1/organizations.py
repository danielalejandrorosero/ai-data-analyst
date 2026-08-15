from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.auth.schemas import OrganizationCreateRequest, OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrganizationOut:
    return await auth_service.create_organization(db, actor=current_user, name=payload.name)
