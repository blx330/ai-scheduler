"""track the window covered by the last successful google busy sync

Planning previously treated "the user has a Google token" as "we know this user's
schedule", so a connected-but-never-synced user was planned as free 24/7. These
columns let planning distinguish connected from actually synced, and bound the
inference to the window that was really fetched.
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_busy_sync_window"
down_revision = "0008_remove_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_connections",
        sa.Column("busy_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_connections",
        sa.Column("busy_synced_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_connections",
        sa.Column("busy_synced_end_at", sa.DateTime(timezone=True), nullable=True),
    )
    # calendar_connections.user_id is filtered on every planning run and every
    # connection lookup; Postgres does not index foreign keys automatically.
    op.create_index(
        "ix_calendar_connection_user_provider",
        "calendar_connections",
        ["user_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_connection_user_provider", table_name="calendar_connections")
    op.drop_column("calendar_connections", "busy_synced_end_at")
    op.drop_column("calendar_connections", "busy_synced_start_at")
    op.drop_column("calendar_connections", "busy_synced_at")
