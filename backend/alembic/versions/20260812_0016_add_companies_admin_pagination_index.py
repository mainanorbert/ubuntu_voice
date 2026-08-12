"""Index the stable ordering used by paginated administrator agent lists.

Revision ID: 20260812_0016
Revises: 20260809_0015
Create Date: 2026-08-12
"""

from alembic import op


revision = "20260812_0016"
down_revision = "20260809_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Support ordered page retrieval without sorting every company row."""
    op.create_index("ix_companies_created_at_id", "companies", ["created_at", "id"])


def downgrade() -> None:
    """Remove the administrator pagination index."""
    op.drop_index("ix_companies_created_at_id", table_name="companies")
