"""enforce one confirmed practice session per (dance_event, session_index)

Confirming was a check-then-insert against a non-unique index, so two concurrent
confirms for the same session both passed the check and both inserted. Only the
database can close that race. Partial on status='confirmed' because unscheduled rows
for the same session are expected to accumulate.

Also indexes the foreign keys used by the room-conflict and run-cleanup paths;
Postgres does not index foreign keys automatically.
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_unique_confirmed_session"
down_revision = "0009_busy_sync_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Collapse any pre-existing duplicates before the constraint goes on, keeping the
    # earliest confirmed row for each session.
    op.execute(
        """
        UPDATE practice_sessions AS duplicate
        SET status = 'unscheduled'
        WHERE duplicate.status = 'confirmed'
          AND duplicate.id <> (
            SELECT keep.id
            FROM practice_sessions AS keep
            WHERE keep.dance_event_id = duplicate.dance_event_id
              AND keep.session_index = duplicate.session_index
              AND keep.status = 'confirmed'
            ORDER BY keep.created_at ASC, keep.id ASC
            LIMIT 1
          )
        """
    )
    op.create_index(
        "uq_practice_session_confirmed",
        "practice_sessions",
        ["dance_event_id", "session_index"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmed'"),
        sqlite_where=sa.text("status = 'confirmed'"),
    )
    op.create_index("ix_practice_session_room", "practice_sessions", ["room_id"])
    op.create_index("ix_dance_event_participant_user", "dance_event_participants", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_dance_event_participant_user", table_name="dance_event_participants")
    op.drop_index("ix_practice_session_room", table_name="practice_sessions")
    op.drop_index("uq_practice_session_confirmed", table_name="practice_sessions")
