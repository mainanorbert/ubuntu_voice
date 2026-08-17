"""Keep displayed and normalized incident place labels consistent.

GPS aggregation is keyed by location, so a later report may update the latest
human-readable place label for an existing hotspot. Ensure its normalized label
is updated at the same time and repair rows written before that behavior.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0018"
down_revision = "20260817_0017"
branch_labels = None
depends_on = None


def _normalize_place(value: str) -> str:
    return " ".join(value.strip().lower().split())


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, place, normalized_place FROM incident_statistics")).mappings()
    for row in rows:
        normalized_place = _normalize_place(row["place"])
        if row["normalized_place"] != normalized_place:
            bind.execute(
                sa.text("UPDATE incident_statistics SET normalized_place = :normalized_place WHERE id = :id"),
                {"id": row["id"], "normalized_place": normalized_place},
            )


def downgrade() -> None:
    # The corrected value is derived data; retaining it is safe on downgrade.
    pass
