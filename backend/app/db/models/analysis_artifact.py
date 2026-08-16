import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtifactType(enum.StrEnum):
    CHART = "CHART"


class AnalysisArtifact(Base):
    """Tablas/graficos/exports producidos por un analysis (RF-041/RF-042,
    Fase 5). Solo `type=CHART` por ahora - `create_chart` es la unica tool
    que produce artifacts; el resultado tabular en si ya vive en
    Analysis.result_json (no se duplica aca).

    `spec_json` es la especificacion del grafico (tipo, ejes, filas) que
    consume un frontend con Recharts - nunca una imagen renderizada.
    `source_sql` es la trazabilidad explicita que pide RF-042 ("ver los
    datos utilizados por el grafico y la consulta origen").
    """

    __tablename__ = "analysis_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[ArtifactType] = mapped_column(
        SAEnum(ArtifactType, name="artifact_type"), nullable=False
    )
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_sql: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
