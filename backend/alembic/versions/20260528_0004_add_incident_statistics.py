"""Add incident statistics table.

Revision ID: 20260528_0004
Revises: 20260510_0003
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260528_0004"
down_revision = "20260510_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the incident statistics aggregation table if needed."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "incident_statistics" in inspector.get_table_names():
        return

    op.create_table(
        "incident_statistics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("place", sa.Text(), nullable=False),
        sa.Column("normalized_place", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('Rights Violations', 'Displacements', 'Casualties', 'Severe Hunger')",
            name="ck_incident_statistics_type",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "normalized_place", "type", name="uq_incident_stats_company_place_type"),
    )
    op.create_index("ix_incident_statistics_company_id", "incident_statistics", ["company_id"])
    op.create_index("ix_incident_statistics_normalized_place", "incident_statistics", ["normalized_place"])
    op.create_index("ix_incident_statistics_updated_at", "incident_statistics", ["updated_at"])


def downgrade() -> None:
    """Drop the incident statistics aggregation table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "incident_statistics" not in inspector.get_table_names():
        return

    op.drop_index("ix_incident_statistics_updated_at", table_name="incident_statistics")
    op.drop_index("ix_incident_statistics_normalized_place", table_name="incident_statistics")
    op.drop_index("ix_incident_statistics_company_id", table_name="incident_statistics")
    op.drop_table("incident_statistics")
