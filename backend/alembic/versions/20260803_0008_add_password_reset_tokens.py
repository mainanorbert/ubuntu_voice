"""Add password-reset token storage.

Revision ID: 20260803_0008
Revises: 20260801_0007
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

revision = "20260803_0008"
down_revision = "20260801_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store only hashed, expiring reset credentials."""
    op.add_column("users", sa.Column("password_reset_token_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_password_reset_token_hash", "users", ["password_reset_token_hash"])


def downgrade() -> None:
    """Remove password-reset token storage."""
    op.drop_index("ix_users_password_reset_token_hash", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token_hash")
