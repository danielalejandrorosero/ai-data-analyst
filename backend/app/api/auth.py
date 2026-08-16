from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    try:
        user_out, token = await auth_service.register(
            db,
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
        )
    except auth_service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado"
        ) from exc

    return TokenResponse(access_token=token, user=user_out)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    try:
        user_out, token = await auth_service.authenticate(
            db, email=payload.email, password=payload.password
        )
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas"
        ) from exc

    return TokenResponse(access_token=token, user=user_out)


@router.get("/me", response_model=UserOut)
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    return await auth_service.build_user_out(db, current_user)
