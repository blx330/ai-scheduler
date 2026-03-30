"""dance planning mvp schema"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_dance_planning_mvp"
down_revision = "0002_google_calendar_demo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dance_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organizer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("latest_schedule_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_session_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dance_event_deadline", "dance_events", ["latest_schedule_at"])
    op.create_index("ix_dance_event_organizer_created", "dance_events", ["organizer_user_id", "created_at"])

    op.create_table(
        "dance_event_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("dance_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dance_event_id", "user_id", name="uq_dance_event_participant"),
    )
    op.create_index("ix_dance_event_participant_role", "dance_event_participants", ["dance_event_id", "role"])

    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "planning_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_step_minutes", sa.Integer(), nullable=False),
        sa.Column("event_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_planning_run_created", "planning_runs", ["created_at"])

    op.create_table(
        "planning_run_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("planning_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("planning_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dance_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_index", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("score_breakdown_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("participant_statuses_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), nullable=False),
        sa.Column("missing_required_user_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("planning_run_id", "dance_event_id", "session_index", "rank", name="uq_planning_result_rank"),
    )
    op.create_index("ix_planning_result_event_session", "planning_run_results", ["dance_event_id", "session_index"])

    op.create_table(
        "practice_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("dance_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dance_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_index", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("planning_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_fallback", sa.Boolean(), nullable=False),
        sa.Column("missing_required_user_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score_breakdown_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_practice_session_event_session", "practice_sessions", ["dance_event_id", "session_index"])
    op.create_index("ix_practice_session_time", "practice_sessions", ["start_at", "end_at"])

    op.get_bind().execute(
        sa.text(
            "INSERT INTO rooms (id, name, is_active, created_at, updated_at) "
            "VALUES (:id, :name, true, NOW(), NOW())"
        ),
        {"id": str(uuid.uuid4()), "name": "Shared Studio"},
    )


def downgrade() -> None:
    op.drop_index("ix_practice_session_time", table_name="practice_sessions")
    op.drop_index("ix_practice_session_event_session", table_name="practice_sessions")
    op.drop_table("practice_sessions")
    op.drop_index("ix_planning_result_event_session", table_name="planning_run_results")
    op.drop_table("planning_run_results")
    op.drop_index("ix_planning_run_created", table_name="planning_runs")
    op.drop_table("planning_runs")
    op.drop_table("rooms")
    op.drop_index("ix_dance_event_participant_role", table_name="dance_event_participants")
    op.drop_table("dance_event_participants")
    op.drop_index("ix_dance_event_organizer_created", table_name="dance_events")
    op.drop_index("ix_dance_event_deadline", table_name="dance_events")
    op.drop_table("dance_events")
