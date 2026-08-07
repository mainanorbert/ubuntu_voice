"""Add admin-controlled agent approval state."""

from alembic import op
import sqlalchemy as sa

revision = "20260807_0012"
down_revision = "20260806_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("companies", sa.Column("approved_by", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_companies_is_approved", "companies", ["is_approved"])


def downgrade() -> None:
    op.drop_index("ix_companies_is_approved", table_name="companies")
    op.drop_column("companies", "approved_at")
    op.drop_column("companies", "approved_by")
    op.drop_column("companies", "is_approved")
