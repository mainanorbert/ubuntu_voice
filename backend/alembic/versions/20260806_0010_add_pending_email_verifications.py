"""Add pending manual-registration email verification storage.

Revision ID: 20260806_0010
Revises: 20260805_0009
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0010"
down_revision = "20260805_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store only hashed, expiring credentials until email ownership is confirmed."""
    op.create_table(
        "pending_email_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(btrim(email)) > 0", name="ck_pending_email_verifications_email_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_pending_email_verifications_token_hash",
        "pending_email_verifications",
        ["token_hash"],
    )


def downgrade() -> None:
    """Remove pending email-verification registrations."""
    op.drop_index("ix_pending_email_verifications_token_hash", table_name="pending_email_verifications")
    op.drop_table("pending_email_verifications")
