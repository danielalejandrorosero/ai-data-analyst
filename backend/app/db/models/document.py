import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Dimension fija del embedding (ADR-0011): cambiar de modelo a otra
# dimension requiere migracion + re-indexar, no solo editar config.
EMBEDDING_DIM = 384


class DocumentStatus(enum.StrEnum):
    """RF-061: la ingesta es asincrona y el estado siempre es visible."""

    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Document(Base):
    """Documento subido para RAG (RF-060). El texto extraido vive en
    document_chunks, no aca - esta fila es el catalogo/estado."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_org_created_at", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # "pdf" / "txt" / "md" / "docx" - RF-060 fija los formatos del MVP.
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.PROCESSING,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Bytes originales SOLO mientras el documento esta en PROCESSING - el
    # worker los consume para extraer/indexar y los limpia al terminar
    # (READY o FAILED). No es storage permanente de archivos (SRS 6.1:
    # nada gigante como columna de una fila mas alla de lo transitorio).
    raw_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentChunk(Base):
    """Fragmento indexado (RF-061/RF-062). No duplica organization_id: el
    filtro de tenant ocurre via JOIN al documento padre - misma excepcion
    aceptada que las tablas hijas de analyses (.claude/rules/database.md)."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
