import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.membership import Role
from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.datasets import service as datasets_service
from app.domain.datasets.schemas import DatasetOut, DatasetSchemaOut

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/import", response_model=DatasetSchemaOut, status_code=status.HTTP_201_CREATED)
async def import_dataset(
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

    datasets = await datasets_service.list_datasets(db, organization_id=organization_id)
    return [DatasetOut.model_validate(dataset) for dataset in datasets]


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
