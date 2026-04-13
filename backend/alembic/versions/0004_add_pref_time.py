"""add user preferred practice time"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_pref_time"
down_revision = "0003_dance_planning_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_practice_time", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferred_practice_time")
