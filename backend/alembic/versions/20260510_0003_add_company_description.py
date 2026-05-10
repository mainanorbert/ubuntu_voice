"""Add optional description to companies.

Revision ID: 20260510_0003
Revises: 20260510_0002
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_0003"
down_revision = "20260510_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a nullable description column so existing company rows remain valid."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("companies")}
    if "description" not in columns:
        op.add_column("companies", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the company description column."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("companies")}
    if "description" in columns:
        op.drop_column("companies", "description")
