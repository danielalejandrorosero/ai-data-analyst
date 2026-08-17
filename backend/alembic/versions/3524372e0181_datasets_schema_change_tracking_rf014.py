"""datasets_schema_change_tracking_rf014

Revision ID: 3524372e0181
Revises: f6f7de135858
Create Date: 2026-08-16 20:14:19.198074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3524372e0181'
down_revision: Union[str, Sequence[str], None] = 'f6f7de135858'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nota: autogenerate tambien detecto un drop de
    # ix_document_chunks_content_fts / ix_document_chunks_embedding como
    # "removidos" - mismo falso positivo de reflexion ya documentado en
    # f6f7de135858 (son un indice GIN sobre expresion y un HNSW de
    # pgvector, autogenerate no los reconstruye identicos al reflejarlos),
    # sin relacion con RF-014. Se descartaron a mano, esta migracion solo
    # agrega las columnas nuevas de datasets.
    op.add_column('datasets', sa.Column('schema_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('datasets', sa.Column('last_schema_change', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('datasets', 'last_schema_change')
    op.drop_column('datasets', 'schema_updated_at')
