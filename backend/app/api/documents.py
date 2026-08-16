import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.arq_pool import get_arq_pool
from app.core.config import settings
from app.db.models.membership import Role
from app.db.models.user import User
from app.db.session import get_db
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.documents import search as search_service
from app.domain.documents import service as documents_service
from app.domain.documents.schemas import DocumentOut, DocumentSearchResultOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    organization_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    """RF-060/RF-061: crea el documento en PROCESSING y encola la ingesta
    en el worker - responde 202 de inmediato, el estado se sigue via
    GET /documents."""
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None or membership.role not in (Role.OWNER, Role.ADMIN, Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    # Tope de lectura antes de bufferizar (mismo patron que datasets.py).
    max_bytes = settings.document_max_file_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    try:
        document = await documents_service.create_document(
            db,
            organization_id=organization_id,
            actor_id=current_user.id,
            filename=file.filename or "documento",
            content=content,
        )
    except documents_service.DocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    pool = await get_arq_pool()
    await pool.enqueue_job("process_document_job", str(document.id))
    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    organization_id: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentOut]:
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    documents = await documents_service.list_documents(db, organization_id=organization_id)
    return [DocumentOut.model_validate(document) for document in documents]


@router.get("/search", response_model=list[DocumentSearchResultOut])
async def search_documents(
    organization_id: Annotated[uuid.UUID, Query()],
    q: Annotated[str, Query(min_length=1, max_length=500)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentSearchResultOut]:
    """RF-062: busqueda hibrida, accesible a cualquier miembro del tenant."""
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    return await search_service.hybrid_search(db, organization_id=organization_id, query=q)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """RF-065: 404 uniforme si no existe o es de otro tenant (mismo
    criterio que GET /datasets/{id}/schema); borrar exige OWNER/ADMIN."""
    document = await documents_service.get_document_by_id(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=document.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    if membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    await documents_service.delete_document(db, document=document, actor_id=current_user.id)
