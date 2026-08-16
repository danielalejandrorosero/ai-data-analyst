import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSource(Base):
    """Origen de un dataset.

    `type` es "upload" (CSV/Excel importado, RF-011) o "postgres" (conexion
    externa, RF-010 - MySQL queda diferido, ver docs/architecture.md
    seccion 8.1). Una unica fila por (organizacion, type) - de ahi el
    UniqueConstraint: evita duplicados por condicion de carrera en
    "upload", y de forma deliberada limita el MVP a una unica conexion
    externa de cada tipo por organizacion (no se pidio soportar multiples
    conexiones del mismo motor en el SRS).

    Las columnas de conexion (host/port/database_name/username) son
    nullable porque la fila "upload" no las usa. La password NUNCA se
    guarda en estas columnas - va cifrada (Fernet, RF-010 "credenciales
    almacenadas de forma segura") en `secret_ref`, con la clave de
    `SECRET_ENCRYPTION_KEY` (ver docs/adr/0004-secrets-management.md).
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
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
