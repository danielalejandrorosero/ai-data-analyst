import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dataset(Base):
    """Entrada de catalogo para un dataset consultable (RF-012).

    `table_name` referencia la tabla fisica real en el schema Postgres
    `datasets` (separado de `public`, donde viven las tablas de la
    plataforma) - ahi es donde vive la data importada, no en esta fila.
    `schema` guarda columnas/tipos inferidos, no la data en si (principio
    de persistencia del SRS seccion 6.1: resultados grandes como
    artefacto/referencia, no como campo gigante en una fila).
    """

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
