import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import key_by_user, limiter
from app.db.models.data_source import DataSource
from app.db.models.membership import Role
from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.datasets import connections as connections_service
from app.domain.datasets import service as datasets_service
from app.domain.datasets.connections import ConnectionTestError
from app.domain.datasets.schemas import (
    DatasetAnnotationUpdate,
    DatasetOut,
    DatasetSchemaOut,
    ExternalConnectionCreateRequest,
    ExternalConnectionOut,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/import", response_model=DatasetSchemaOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_expensive, key_func=key_by_user)
async def import_dataset(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    organization_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
) -> DatasetSchemaOut:
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None or membership.role not in (Role.OWNER, Role.ADMIN, Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    # Tope de lectura ANTES de bufferizar todo a memoria (RNF-014): un
    # archivo de cualquier tamano real solo consume, como maximo,
    # max_bytes + 1 - el chequeo de tamano en el servicio queda como
    # backstop, no como unico control.
    max_bytes = settings.import_max_file_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    try:
        return await datasets_service.import_file(
            db,
            organization_id=organization_id,
            actor_id=current_user.id,
            filename=file.filename or "dataset",
            content=content,
            dataset_name=name,
        )
    except datasets_service.DatasetImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("", response_model=list[DatasetOut])
async def list_datasets(
    organization_id: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DatasetOut]:
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    rows = await datasets_service.list_datasets(db, organization_id=organization_id)
    return [
        DatasetOut(
            id=dataset.id,
            organization_id=dataset.organization_id,
            source_id=dataset.source_id,
            source_type=source_type,
            source_extension=dataset.source_extension,
            name=dataset.name,
            description=dataset.description,
            row_count=dataset.row_count,
            column_count=len(dataset.schema_json),
            created_at=dataset.created_at,
        )
        for dataset, source_type in rows
    ]


@router.post(
    "/connections", response_model=ExternalConnectionOut, status_code=status.HTTP_201_CREATED
)
async def register_connection(
    payload: ExternalConnectionCreateRequest,
    organization_id: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ExternalConnectionOut:
    """RF-010 / CU-03. Solo OWNER/ADMIN pueden registrar conexiones
    externas. La conexion se prueba con un SELECT 1 controlado ANTES de
    guardar nada - si falla, no queda ningun rastro de las credenciales
    (ni siquiera cifradas)."""
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None or membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    try:
        await connections_service.test_postgres_connection(payload)
    except ConnectionTestError as exc:
        await connections_service.record_connection_test_failure(
            db, organization_id=organization_id, actor_id=current_user.id, payload=payload
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    source = await connections_service.register_external_connection(
        db, organization_id=organization_id, actor_id=current_user.id, payload=payload
    )
    return ExternalConnectionOut.model_validate(source)


@router.get("/{dataset_id}/schema", response_model=DatasetSchemaOut)
async def get_dataset_schema(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DatasetSchemaOut:
    dataset = await datasets_service.get_dataset_by_id(db, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=dataset.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")

    return datasets_service.build_dataset_schema_out(dataset)


@router.patch("/{dataset_id}/annotations", response_model=DatasetOut)
async def update_dataset_annotations(
    dataset_id: uuid.UUID,
    payload: DatasetAnnotationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DatasetOut:
    """RF-013: etiquetar el dataset y/o columnas puntuales con metadatos
    semanticos (texto libre) que el agente usa como contexto adicional al
    inspeccionar el esquema."""
    dataset = await datasets_service.get_dataset_by_id(db, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=dataset.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    if membership.role not in (Role.OWNER, Role.ADMIN, Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    dataset = await datasets_service.update_dataset_annotations(
        db, dataset=dataset, payload=payload, actor_id=current_user.id
    )

    source_type = await db.scalar(select(DataSource.type).where(DataSource.id == dataset.source_id))
    return DatasetOut(
        id=dataset.id,
        organization_id=dataset.organization_id,
        source_id=dataset.source_id,
        source_type=source_type or "",
        source_extension=dataset.source_extension,
        name=dataset.name,
        description=dataset.description,
        row_count=dataset.row_count,
        column_count=len(dataset.schema_json),
        created_at=dataset.created_at,
    )
