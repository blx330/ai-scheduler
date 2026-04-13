"""add raw parsed user practice prefs"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_user_prefs_text"
down_revision = "0005_dance_spacing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_practice_time_raw", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "preferred_practice_time_parsed",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_practice_time_parsed")
    op.drop_column("users", "preferred_practice_time_raw")
