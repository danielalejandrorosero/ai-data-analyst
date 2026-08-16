import uuid

from app.db.models.document import Document, DocumentStatus
from app.db.session import async_session_maker
from app.domain.documents.service import process_document
from sqlalchemy import select


async def process_document_job(ctx: dict, document_id: str) -> None:  # noqa: ARG001 - ctx lo exige ARQ
    """RF-061: ingesta asincrona de un documento (extraer -> fragmentar ->
    embeber -> indexar). Toda la logica vive en
    domain/documents/service.py (que garantiza estado terminal READY/
    FAILED siempre); este job solo resuelve la entidad y la pasa."""
    async with async_session_maker() as db:
        document = (
            await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        ).scalar_one_or_none()
        if document is None or document.status != DocumentStatus.PROCESSING:
            # Borrado antes de procesarse, o job re-entregado por ARQ
            # despues de completarse - no hay nada que hacer.
            return
        await process_document(db, document)
