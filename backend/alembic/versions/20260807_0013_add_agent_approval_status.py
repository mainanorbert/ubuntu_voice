"""Track pending and suspended agent states separately."""

from alembic import op
import sqlalchemy as sa

revision = "20260807_0013"
down_revision = "20260807_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("approval_status", sa.Text(), nullable=True, server_default="approved"),
    )
    op.execute(
        "UPDATE companies SET approval_status = 'unapproved' "
        "WHERE is_approved = false"
    )
    op.alter_column(
        "companies",
        "approval_status",
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("companies", "approval_status")
