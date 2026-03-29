"""google calendar demo support"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_google_calendar_demo"
down_revision = "0001_pass2_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calendar_connections", sa.Column("access_token", sa.Text(), nullable=True))
    op.add_column("calendar_connections", sa.Column("refresh_token", sa.Text(), nullable=True))
    op.add_column("calendar_connections", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calendar_connections", sa.Column("scopes", sa.Text(), nullable=True))
    op.add_column("calendar_connections", sa.Column("account_email", sa.String(length=255), nullable=True))
    op.add_column(
        "calendar_connections",
        sa.Column("selected_busy_calendar_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column("calendar_connections", sa.Column("selected_write_calendar_id", sa.String(length=255), nullable=True))
    op.alter_column("calendar_connections", "selected_busy_calendar_ids_json", server_default=None)

    op.add_column(
        "schedule_requests",
        sa.Column("preferred_weekdays_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column("schedule_requests", sa.Column("preferred_time_range_start_local", sa.Time(), nullable=True))
    op.add_column("schedule_requests", sa.Column("preferred_time_range_end_local", sa.Time(), nullable=True))
    op.alter_column("schedule_requests", "preferred_weekdays_json", server_default=None)


def downgrade() -> None:
    op.drop_column("schedule_requests", "preferred_time_range_end_local")
    op.drop_column("schedule_requests", "preferred_time_range_start_local")
    op.drop_column("schedule_requests", "preferred_weekdays_json")

    op.drop_column("calendar_connections", "selected_write_calendar_id")
    op.drop_column("calendar_connections", "selected_busy_calendar_ids_json")
    op.drop_column("calendar_connections", "account_email")
    op.drop_column("calendar_connections", "scopes")
    op.drop_column("calendar_connections", "token_expires_at")
    op.drop_column("calendar_connections", "refresh_token")
    op.drop_column("calendar_connections", "access_token")
