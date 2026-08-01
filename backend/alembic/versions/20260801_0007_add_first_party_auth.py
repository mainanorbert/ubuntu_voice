"""Add first-party manual and Google auth fields.

Revision ID: 20260801_0007
Revises: 20260731_0006
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260801_0007"
down_revision = "20260731_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable auth-linking columns without rewriting existing user ownership."""
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")])


def downgrade() -> None:
    """Remove first-party auth-linking columns."""
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "name")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "password_hash")
