"""Add known places reference table."""

from alembic import op
import sqlalchemy as sa

revision = "20260805_0009"
down_revision = "20260803_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "known_places",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_known_places_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_known_places_longitude"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("known_places")
