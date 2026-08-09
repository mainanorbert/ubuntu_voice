"""Bound company names so their unique index remains safe.

Revision ID: 20260809_0015
Revises: 20260809_0014
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0015"
down_revision = "20260809_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enforce the API's 255-character company-name limit in PostgreSQL."""
    op.alter_column(
        "companies",
        "name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="name::varchar(255)",
    )


def downgrade() -> None:
    """Restore the former unbounded company-name column."""
    op.alter_column(
        "companies",
        "name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using="name::text",
    )
