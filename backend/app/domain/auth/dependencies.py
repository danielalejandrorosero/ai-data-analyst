import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.membership import Membership, Role
from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.security import InvalidTokenError, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido"
        ) from exc

    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado"
        )

    return user


def require_membership(*allowed_roles: Role):
    """Dependencia que exige que el usuario autenticado tenga membership en
    `organization_id` (path param) con uno de los roles permitidos.

    Implementa RF-002 (RBAC) + RF-003 (aislamiento por tenant) en un mismo
    punto: sin membership en esa organizacion -> 403, igual que con un rol
    insuficiente — no se distingue "no existe" de "no tenes acceso" en la
    respuesta, para no filtrar la existencia de organizaciones ajenas.
    """

    async def dependency(
        organization_id: Annotated[uuid.UUID, Path()],
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> Membership:
        membership = await auth_service.get_membership(
            db, user_id=current_user.id, organization_id=organization_id
        )
        if membership is None or (allowed_roles and membership.role not in allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
        return membership

    return dependency
