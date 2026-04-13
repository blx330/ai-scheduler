"""store google ids on practice sessions"""

from alembic import op
import sqlalchemy as sa


revision = "0007_practice_sync"
down_revision = "0006_user_prefs_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practice_sessions", sa.Column("google_calendar_event_id", sa.String(length=255), nullable=True))
    op.add_column("practice_sessions", sa.Column("google_calendar_id", sa.String(length=255), nullable=True))
    op.add_column("practice_sessions", sa.Column("google_calendar_html_link", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("practice_sessions", "google_calendar_html_link")
    op.drop_column("practice_sessions", "google_calendar_id")
    op.drop_column("practice_sessions", "google_calendar_event_id")
