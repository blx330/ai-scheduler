"""remove legacy meeting scheduler tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_remove_legacy_scheduler_tables"
down_revision = "0007_practice_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("schedule_run_results")
    op.drop_index("ix_schedule_run_request_created", table_name="schedule_runs")
    op.drop_table("schedule_runs")
    op.drop_index("ix_schedule_request_participant_request_role", table_name="schedule_request_participants")
    op.drop_table("schedule_request_participants")
    op.drop_index("ix_schedule_request_organizer_created", table_name="schedule_requests")
    op.drop_table("schedule_requests")
    op.drop_index("ix_parsed_preference_user_created", table_name="user_parsed_preferences")
    op.drop_table("user_parsed_preferences")
    op.drop_index("ix_preference_input_user_created", table_name="user_preference_inputs")
    op.drop_table("user_preference_inputs")


def downgrade() -> None:
    op.create_table(
        "user_preference_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_preference_input_user_created", "user_preference_inputs", ["user_id", "created_at"])

    op.create_table(
        "user_parsed_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "preference_input_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_preference_inputs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("constraints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parsed_preference_user_created", "user_parsed_preferences", ["user_id", "created_at"])

    op.create_table(
        "schedule_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("organizer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_step_minutes", sa.Integer(), nullable=False),
        sa.Column("daily_window_start_local", sa.Time(), nullable=True),
        sa.Column("daily_window_end_local", sa.Time(), nullable=True),
        sa.Column("preferred_weekdays_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preferred_time_range_start_local", sa.Time(), nullable=True),
        sa.Column("preferred_time_range_end_local", sa.Time(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schedule_request_organizer_created", "schedule_requests", ["organizer_user_id", "created_at"])

    op.create_table(
        "schedule_request_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "schedule_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedule_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_request_id", "user_id", name="uq_schedule_request_participant"),
    )
    op.create_index(
        "ix_schedule_request_participant_request_role",
        "schedule_request_participants",
        ["schedule_request_id", "role"],
    )

    op.create_table(
        "schedule_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "schedule_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedule_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schedule_run_request_created", "schedule_runs", ["schedule_request_id", "created_at"])

    op.create_table(
        "schedule_run_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("schedule_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schedule_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("score_breakdown_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.String(length=500), nullable=False),
        sa.Column("required_participants_satisfied", sa.Boolean(), nullable=False),
        sa.Column("optional_available_count", sa.Integer(), nullable=False),
        sa.Column("participant_statuses_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_run_id", "rank", name="uq_schedule_run_rank"),
        sa.UniqueConstraint("schedule_run_id", "start_at", "end_at", name="uq_schedule_run_slot"),
    )
