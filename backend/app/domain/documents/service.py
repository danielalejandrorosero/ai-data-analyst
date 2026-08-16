import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.document import Document, DocumentChunk, DocumentStatus
from app.domain.audit import service as audit_service
from app.domain.documents import embeddings
from app.domain.documents.extraction import (
    SUPPORTED_FORMATS,
    TextExtractionError,
    chunk_text,
    extract_text,
)

logger = logging.getLogger("app.documents")


class DocumentError(Exception):
    """Rechazo de negocio (formato, tamano, contenido) - se traduce a 422."""


async def create_document(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> Document:
    """RF-060: valida y deja el documento en PROCESSING con los bytes
    originales a bordo - la extraccion/indexado real ocurre en el worker
    (RF-061), nunca en el request de subida."""
    lower = filename.lower()
    if "." not in lower:
        raise DocumentError("El archivo no tiene extension")
    extension = lower.rsplit(".", 1)[1]
    if extension not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise DocumentError(f"Formato no soportado: .{extension} (aceptados: {supported})")

    max_bytes = settings.document_max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise DocumentError(
            f"El archivo supera el limite de {settings.document_max_file_size_mb}MB"
        )
    if not content:
        raise DocumentError("El archivo esta vacio")

    document = Document(
        organization_id=organization_id,
        uploaded_by=actor_id,
        filename=filename,
        file_format=extension,
        size_bytes=len(content),
        status=DocumentStatus.PROCESSING,
        raw_content=content,
    )
    db.add(document)
    await db.flush()

    await audit_service.record_event(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        action="document.upload",
        target=f"document:{document.id}",
    )
    await db.commit()
    return document


async def list_documents(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.organization_id == organization_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars())


async def get_document_by_id(db: AsyncSession, document_id: uuid.UUID) -> Document | None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def delete_document(db: AsyncSession, *, document: Document, actor_id: uuid.UUID) -> None:
    """RF-065: los chunks caen por ON DELETE CASCADE."""
    await audit_service.record_event(
        db,
        organization_id=document.organization_id,
        actor_id=actor_id,
        action="document.delete",
        target=f"document:{document.id}",
    )
    await db.delete(document)
    await db.commit()


async def process_document(db: AsyncSession, document: Document) -> None:
    """RF-061 (corre en el worker): extrae, fragmenta, embebe e indexa.
    Deja el documento en READY o FAILED SIEMPRE - nunca colgado en
    PROCESSING - y limpia raw_content en ambos casos."""
    try:
        if document.raw_content is None:
            raise TextExtractionError("El documento no tiene contenido pendiente de procesar")

        text = extract_text(document.raw_content, document.file_format)
        chunks = chunk_text(
            text,
            max_chars=settings.document_chunk_chars,
            overlap=settings.document_chunk_overlap_chars,
        )
        if not chunks:
            raise TextExtractionError("El documento no produjo ningun fragmento indexable")

        vectors = await asyncio.to_thread(embeddings.embed_texts, chunks)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=vector,
                )
            )

        document.chunk_count = len(chunks)
        document.status = DocumentStatus.READY
        document.error = None
    except TextExtractionError as exc:
        document.status = DocumentStatus.FAILED
        document.error = str(exc)
        logger.warning("document.failed document_id=%s error=%s", document.id, exc)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo deja FAILED, no un documento colgado
        document.status = DocumentStatus.FAILED
        # Mismo criterio que orchestrator.py: `error` es visible para todo
        # miembro de la organizacion, un fallo no anticipado no expone
        # detalles internos - el detalle real va al log del worker.
        document.error = "Ocurrio un error inesperado al procesar el documento"
        logger.error("document.failed document_id=%s error=%r", document.id, exc, exc_info=True)

    document.raw_content = None
    await db.commit()
