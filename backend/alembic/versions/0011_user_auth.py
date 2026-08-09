"""add user role and google login identity

role gates organizer-only actions in the new auth layer; google_subject_id links a
users row to a Google account once someone logs in with that email, so later logins
match by subject id even if the Google account's email changes.
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_user_auth"
down_revision = "0010_unique_confirmed_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
    )
    op.add_column(
        "users",
        sa.Column("google_subject_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint("uq_users_google_subject_id", "users", ["google_subject_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_google_subject_id", "users", type_="unique")
    op.drop_column("users", "google_subject_id")
    op.drop_column("users", "role")
