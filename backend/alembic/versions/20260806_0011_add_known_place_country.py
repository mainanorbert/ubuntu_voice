"""Add optional country metadata to known places.

Revision ID: 20260806_0011
Revises: 20260806_0010
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0011"
down_revision = "20260806_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("known_places", sa.Column("country", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("known_places", "country")
