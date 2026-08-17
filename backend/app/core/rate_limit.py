from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.domain.auth.security import InvalidTokenError, decode_access_token

# Gap de seguridad de docs/security/threat-model.md: rate limiting con
# slowapi, backend Redis (reusa settings.redis_url - mismo Redis que ARQ y
# app/core/redis_client.py, no un store nuevo).
#
# key_func por defecto (IP) para endpoints publicos como /auth/login y
# /auth/register.
#
# headers_enabled=False (default de slowapi, explicito aca): los endpoints
# de esta API devuelven schemas Pydantic (via response_model), no un
# starlette.Response - slowapi._inject_headers() solo sabe escribir los
# X-RateLimit-* en un Response real, y explota si el valor de retorno del
# endpoint no lo es (ver slowapi.extension.Limiter._inject_headers). No
# hace falta para cumplir el requisito (429 al exceder el limite), asi que
# se deja apagado en vez de forzar a cada endpoint a aceptar un parametro
# `response: Response` solo para esto.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    enabled=settings.rate_limit_enabled,
)


def key_by_user(request: Request) -> str:
    """key_func para endpoints autenticados (import/documents/search).

    slowapi solo le pasa el `Request` al key_func (ver
    slowapi.extension.Limiter.__evaluate_limits) - no tiene acceso a las
    dependencies de FastAPI ya resueltas (`current_user`), asi que no
    podemos simplemente reusar `get_current_user`. Decodificamos el JWT
    directamente (mismo decode_access_token que domain/auth/dependencies.py,
    sin tocar la DB: alcanza con el 'sub' del token para armar la key de
    rate limit). Si el token es invalido/falta, get_current_user va a
    rechazar la request con 401 de todas formas antes de que corra logica
    de negocio - el fallback a IP aca es solo para no mandarle una key
    vacia a slowapi.
    """
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            user_id = decode_access_token(token)
        except InvalidTokenError:
            pass
        else:
            return f"user:{user_id}"

    return f"ip:{get_remote_address(request)}"
