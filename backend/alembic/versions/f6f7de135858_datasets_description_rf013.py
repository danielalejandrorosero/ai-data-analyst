"""datasets_description_rf013

Revision ID: f6f7de135858
Revises: c07af8be762c
Create Date: 2026-08-16 16:39:59.462172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6f7de135858'
down_revision: Union[str, Sequence[str], None] = 'c07af8be762c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nota: autogenerate tambien detecto un drop de
    # ix_document_chunks_content_fts / ix_document_chunks_embedding como
    # "removidos" - falso positivo de reflexion (son un indice GIN sobre
    # expresion y un HNSW de pgvector, autogenerate no los reconstruye
    # identicos al reflejarlos) sin relacion con RF-013. Se descartaron a
    # mano, esta migracion solo agrega la columna nueva.
    op.add_column('datasets', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('datasets', 'description')
