import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretDecryptionError(Exception):
    """El ciphertext no pudo descifrarse (clave rotada, dato corrupto, etc.)."""


def _fernet() -> Fernet:
    """Deriva una clave Fernet valida (32 bytes urlsafe-base64) a partir de
    SECRET_ENCRYPTION_KEY, que es un string arbitrario en .env - no se le
    exige el formato especifico que pide Fernet directamente."""
    digest = hashlib.sha256(settings.secret_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """RF-010 ("credenciales almacenadas de forma segura"): cifrado a nivel
    de aplicacion (ADR-0004) sobre data_sources.secret_ref. Nunca se guarda
    la password en texto plano en ninguna columna ni log."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "No se pudo descifrar el secreto (clave rotada o dato corrupto)"
        ) from exc
