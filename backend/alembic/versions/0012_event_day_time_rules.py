"""add organizer day/time rules to dance events

Hard rules set by the organizer (typically from a plain-English scheduling
request): allowed and blocked weekdays, and an organizer-local time window.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_event_day_time_rules"
down_revision = "0011_user_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dance_events",
        sa.Column("allowed_weekdays_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "dance_events",
        sa.Column("blocked_weekdays_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("dance_events", sa.Column("earliest_start_time_local", sa.Time(), nullable=True))
    op.add_column("dance_events", sa.Column("latest_end_time_local", sa.Time(), nullable=True))
    op.alter_column("dance_events", "allowed_weekdays_json", server_default=None)
    op.alter_column("dance_events", "blocked_weekdays_json", server_default=None)


def downgrade() -> None:
    op.drop_column("dance_events", "latest_end_time_local")
    op.drop_column("dance_events", "earliest_start_time_local")
    op.drop_column("dance_events", "blocked_weekdays_json")
    op.drop_column("dance_events", "allowed_weekdays_json")
