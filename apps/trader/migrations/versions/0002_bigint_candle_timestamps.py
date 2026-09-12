"""Allow Binance millisecond timestamps in signals and intents."""
import sqlalchemy as sa
from alembic import op


revision = "0002_bigint_candle_timestamps"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _alter(table: str, direction: str) -> None:
    bind = op.get_bind()
    target_type = sa.BigInteger() if direction == "up" else sa.Integer()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("candle_timestamp", existing_type=sa.Integer(), type_=target_type)
    else:
        op.alter_column(table, "candle_timestamp", existing_type=sa.Integer(), type_=target_type)


def upgrade() -> None:
    _alter("signals", "up")
    _alter("trade_intents", "up")


def downgrade() -> None:
    _alter("trade_intents", "down")
    _alter("signals", "down")
