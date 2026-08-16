import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

from app.core.config import settings

_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        # Cubre password incorrecta (VerifyMismatchError, subclase de
        # Argon2Error) y tambien un hash corrupto/invalido en la DB
        # (InvalidHashError - OJO: esta NO hereda de Argon2Error, hereda
        # de ValueError, hay que capturarla aparte). En ambos casos el
        # resultado correcto es "no autenticado", no un 500.
        return False


# Hash dummy fijo, calculado una sola vez al importar. Se usa para que
# verificar contra un email que no existe cueste lo mismo (Argon2id) que
# verificar contra uno que si existe - sin esto, la ausencia de llamada a
# verify_password() cuando el usuario no existe crea una diferencia de
# tiempo medible que permite enumerar emails registrados (RNF-012).
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-constant-time-auth")


def verify_dummy_password(password: str) -> None:
    verify_password(password, _DUMMY_PASSWORD_HASH)


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
