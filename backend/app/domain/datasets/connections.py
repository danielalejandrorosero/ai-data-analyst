import asyncio
import ipaddress
import socket
import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.crypto import encrypt_secret
from app.db.models.data_source import DataSource
from app.domain.audit import service as audit_service
from app.domain.datasets.schemas import ExternalConnectionCreateRequest

# Timeout corto y fijo para la prueba de conexion (RF-010: "se verifica con
# una prueba controlada") - esto nunca es la conexion que despues usa el
# agente para consultar (esa es otra historia, cuando el agente soporte
# fuentes externas ademas de datasets importados).
CONNECTION_TEST_TIMEOUT_SECONDS = 5

# Mensaje unico para TODO fallo de test_postgres_connection (host interno
# bloqueado, DNS que no resuelve, credenciales invalidas, timeout, DSN mal
# formado, lo que sea) - un mensaje distinto por causa seria un oraculo que
# permite mapear la red interna (rango bloqueado vs. intento real fallido).
_GENERIC_FAILURE_MESSAGE = "No se pudo establecer conexion con las credenciales provistas"


class ConnectionTestError(Exception):
    """La conexion con las credenciales dadas fallo (host, credenciales,
    red, etc.) - nunca se persiste una conexion sin antes probarla."""


async def _assert_host_is_not_internal(host: str, port: int) -> None:
    """Defensa contra SSRF: el endpoint deja que cualquier OWNER/ADMIN
    self-service pida al backend que se conecte a un host/puerto
    arbitrario. Sin esto, ese mismo backend se puede usar como proxy para
    sondear la red interna del despliegue (otros contenedores, servicios
    internos, endpoints de metadata de nube tipo 169.254.169.254).
    Resuelve DNS y rechaza si CUALQUIERA de las IPs resueltas cae en un
    rango privado/loopback/link-local/reservado - antes de intentar
    conectar, asi que nunca hay una conexion TCP real hacia ahi."""
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ConnectionTestError(_GENERIC_FAILURE_MESSAGE) from exc

    for info in infos:
        raw_ip = info[4][0]
        ip = ipaddress.ip_address(raw_ip)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ConnectionTestError(_GENERIC_FAILURE_MESSAGE)


def _postgres_url(payload: ExternalConnectionCreateRequest) -> URL:
    # URL.create escapa cada componente por separado - un f-string manual
    # rompe el parseo (y puede hacer smuggling de otro host) si username o
    # password contienen "@", ":", "/", etc.
    return URL.create(
        drivername="postgresql+asyncpg",
        username=payload.username,
        password=payload.password.get_secret_value(),
        host=payload.host,
        port=payload.port,
        database=payload.database_name,
    )


async def test_postgres_connection(payload: ExternalConnectionCreateRequest) -> None:
    """Prueba controlada (RF-010): un SELECT 1 de solo lectura, nunca una
    consulta que toque datos. Nunca expone al caller la excepcion cruda del
    driver ni la connection string - solo _GENERIC_FAILURE_MESSAGE."""
    await _assert_host_is_not_internal(payload.host, payload.port)

    try:
        engine = create_async_engine(
            _postgres_url(payload),
            connect_args={"timeout": CONNECTION_TEST_TIMEOUT_SECONDS},
        )
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
    except Exception as exc:  # noqa: BLE001 - cualquier fallo (conexion, DSN, driver) es un fallo de negocio
        raise ConnectionTestError(_GENERIC_FAILURE_MESSAGE) from exc


async def record_connection_test_failure(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: ExternalConnectionCreateRequest,
) -> None:
    """Los intentos fallidos son exactamente los que se usarian para sondear
    la red interna (SSRF) - sin esto no quedaba ningun rastro auditable de
    ellos. Nunca incluye la password, ni cifrada."""
    await audit_service.record_event(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        action="connection.test_failed",
        target=f"postgres:{payload.host}:{payload.port}",
    )
    await db.commit()


async def register_external_connection(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: ExternalConnectionCreateRequest,
) -> DataSource:
    """RF-010: registra una conexion externa ya validada (el caller debe
    haber llamado a test_postgres_connection antes - separado para que el
    router pueda devolver un 422 claro sin ensuciar esta funcion con
    HTTPException, que es una responsabilidad de la capa de API)."""
    secret_ciphertext = encrypt_secret(payload.password.get_secret_value())
    insert_stmt = (
        pg_insert(DataSource)
        .values(
            organization_id=organization_id,
            type=payload.type,
            status="active",
            secret_ref=secret_ciphertext,
            name=payload.name,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            username=payload.username,
        )
        .on_conflict_do_update(
            constraint="uq_data_source_org_type",
            set_={
                "status": "active",
                "secret_ref": secret_ciphertext,
                "name": payload.name,
                "host": payload.host,
                "port": payload.port,
                "database_name": payload.database_name,
                "username": payload.username,
            },
        )
        .returning(DataSource)
    )
    result = await db.execute(insert_stmt)
    source = result.scalar_one()

    await audit_service.record_event(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        action="connection.register",
        target=f"data_source:{source.id}",
    )
    await db.commit()
    await db.refresh(source)

    return source
