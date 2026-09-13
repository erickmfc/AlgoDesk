"""Persist Testnet reconciliation state in worker snapshots."""

from alembic import op
import sqlalchemy as sa


revision = "0004_reconcile_snapshots"
down_revision = "0003_runtime_snapshot_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portfolio_snapshots",
        sa.Column("reconciliation_status", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("last_reconciliation_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_snapshots", "last_reconciliation_at")
    op.drop_column("portfolio_snapshots", "reconciliation_status")
