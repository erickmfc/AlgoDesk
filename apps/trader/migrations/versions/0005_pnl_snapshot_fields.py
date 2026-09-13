"""Persist realized and mark-to-market PnL in runtime snapshots."""

from alembic import op
import sqlalchemy as sa


revision = "0005_pnl_snapshot_fields"
down_revision = "0004_reconcile_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("starting_equity", "unrealized_pnl", "total_pnl"):
        op.add_column(
            "portfolio_snapshots",
            sa.Column(name, sa.Float(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    for name in ("total_pnl", "unrealized_pnl", "starting_equity"):
        op.drop_column("portfolio_snapshots", name)
