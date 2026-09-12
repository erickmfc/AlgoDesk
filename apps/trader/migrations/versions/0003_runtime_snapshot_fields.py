"""Persist enough worker state for a stateless API process."""

import sqlalchemy as sa
from alembic import op


revision = "0003_runtime_snapshot_fields"
down_revision = "0002_bigint_candle_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portfolio_snapshots",
        sa.Column(
            "source",
            sa.String(length=64),
            server_default="paper-engine-from-binance-klines",
            nullable=False,
        ),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("allocation_percent", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("trades", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("win_rate", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("status", sa.String(length=24), server_default="running", nullable=False),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("hard_stop", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "portfolio_snapshots", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("last_candle_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots", sa.Column("last_error", sa.Text(), nullable=True)
    )
    op.add_column(
        "portfolio_snapshots", sa.Column("cycles", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "portfolio_snapshots", sa.Column("errors", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    for name in (
        "errors",
        "cycles",
        "last_error",
        "last_candle_at",
        "last_run_at",
        "hard_stop",
        "status",
        "win_rate",
        "trades",
        "allocation_percent",
        "source",
    ):
        op.drop_column("portfolio_snapshots", name)
