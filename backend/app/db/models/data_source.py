import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSource(Base):
    """Origen de un dataset.

    Para el MVP el unico `type` real es "upload" (CSV/Excel importado,
    ver RF-011) - se reutiliza una unica fila "upload" por organizacion,
    de ahi el UniqueConstraint (evita duplicados por condicion de carrera
    en imports concurrentes del primer dataset de una org nueva).
    Conexiones externas (PostgreSQL/MySQL, RF-010) se agregan en Fase 3,
    cuando el agente ejecuta SQL de verdad contra ellas - `secret_ref`
    queda reservado para ese momento: es el CIPHERTEXT cifrado a nivel de
    aplicacion en si (no un puntero/ID a un secret manager externo), ver
    docs/adr/0004-secrets-management.md.
    """

    __tablename__ = "data_sources"
    __table_args__ = (UniqueConstraint("organization_id", "type", name="uq_data_source_org_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
