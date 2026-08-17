"""Keep text place normalization only for the non-GPS fallback path."""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0019"
down_revision = "20260817_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE incident_statistics SET normalized_place = '' WHERE location_source = 'gps'")
    )


def downgrade() -> None:
    # GPS rows intentionally have no normalized text place to restore.
    pass
