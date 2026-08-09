"""Persist server-owned direct-upload confirmation tickets.

Revision ID: 20260809_0014
Revises: 20260807_0013
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0014"
down_revision = "20260807_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create immutable ticket records used to authorize direct confirmations."""
    op.create_table(
        "direct_upload_tickets",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_direct_upload_tickets_company_owner",
        "direct_upload_tickets",
        ["company_id", "uploaded_by"],
    )
    op.create_index(
        "ix_direct_upload_tickets_uploaded_by",
        "direct_upload_tickets",
        ["uploaded_by"],
    )


def downgrade() -> None:
    """Remove direct-upload tickets when rolling back this feature."""
    op.drop_index("ix_direct_upload_tickets_uploaded_by", table_name="direct_upload_tickets")
    op.drop_index("ix_direct_upload_tickets_company_owner", table_name="direct_upload_tickets")
    op.drop_table("direct_upload_tickets")
