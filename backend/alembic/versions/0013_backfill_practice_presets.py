"""backfill retired preferred_practice_time presets

The early_morning/mid_morning/late_morning presets were replaced by
morning/afternoon/evening/late_night blocks without a data migration, so
existing rows still holding an old value fail Pydantic validation on read
(UserRead is a strict enum) and 500 the whole /users list for everyone --
not just the affected row. All three retired presets fell within 8am-noon,
which is exactly the new "morning" window, so backfilling them to "morning"
is a faithful match.
"""

from alembic import op


revision = "0013_backfill_practice_presets"
down_revision = "0012_event_day_time_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET preferred_practice_time = 'morning'
        WHERE preferred_practice_time IN ('early_morning', 'mid_morning', 'late_morning')
        """
    )


def downgrade() -> None:
    # Lossy: the original three-way split (early/mid/late morning) can't be
    # reconstructed from the merged "morning" value, so there's no true inverse.
    pass
