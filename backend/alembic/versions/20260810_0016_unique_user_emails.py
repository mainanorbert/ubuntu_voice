"""Enforce case-insensitive uniqueness for user email addresses.

Revision ID: 20260810_0016
Revises: 20260809_0015
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260810_0016"
down_revision = "20260809_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace the lookup index with a database-enforced unique index."""
    op.drop_index("ix_users_email_lower", table_name="users")
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    """Restore the non-unique email lookup index."""
    op.drop_index("uq_users_email_lower", table_name="users")
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")])
