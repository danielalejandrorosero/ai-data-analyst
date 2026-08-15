import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_token_expire_minutes),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError("token sin 'sub'")

    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise InvalidTokenError("'sub' no es un UUID valido") from exc
