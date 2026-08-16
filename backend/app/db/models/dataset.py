import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dataset(Base):
    """Entrada de catalogo para un dataset consultable (RF-012).

    `table_name` referencia la tabla fisica real en el schema Postgres
    `datasets` (separado de `public`, donde viven las tablas de la
    plataforma) - ahi es donde vive la data importada, no en esta fila.
    Esas tablas fisicas viven FUERA del ciclo de vida de Alembic (se crean
    en runtime, ver domain/datasets/service.py) - un `alembic downgrade`
    de esta migracion borra solo el catalogo, no los datos fisicos. Ver
    docs/architecture.md seccion sobre datasets.
    `schema_json` guarda columnas/tipos inferidos, no la data en si
    (principio de persistencia del SRS seccion 6.1: resultados grandes
    como artefacto/referencia, no como campo gigante en una fila).
    """

    __tablename__ = "datasets"
    __table_args__ = (Index("ix_datasets_org_created_at", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Extension del archivo original ("csv"/"xlsx") para datasets de tipo
    # "upload" - nullable porque no aplica a datasets de otro origen (ni a
    # las filas creadas antes de esta columna). Solo para mostrar el
    # icono correcto en el catalogo (RF-012), no afecta como se lee la
    # tabla fisica ya creada.
    source_extension: Mapped[str | None] = mapped_column(String(10), nullable=True)
    schema_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
