"""Bootstrap the SQLAlchemy trading schema.

The first revision intentionally delegates table creation to the canonical
metadata so SQLite development and PostgreSQL deployment start from exactly
the same model. Future revisions should use explicit Alembic operations.
"""
from alembic import op

from src.models import Base


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
