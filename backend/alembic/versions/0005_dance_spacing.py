"""add dance spacing constraints"""

from alembic import op
import sqlalchemy as sa


revision = "0005_dance_spacing"
down_revision = "0004_add_pref_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dance_events", sa.Column("earliest_start_date", sa.Date(), nullable=True))
    op.add_column(
        "dance_events",
        sa.Column("min_days_apart", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.alter_column("dance_events", "min_days_apart", server_default=None)


def downgrade() -> None:
    op.drop_column("dance_events", "min_days_apart")
    op.drop_column("dance_events", "earliest_start_date")
