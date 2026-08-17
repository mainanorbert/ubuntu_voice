"""Add privacy-preserving location snapshots to incident statistics.

GPS coordinates are rounded to an approximately 100-metre grid by the service
before storage. Existing rows remain valid and are backfilled from known places
where their normalized names match.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0017"
down_revision = "20260812_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident_statistics") as batch_op:
        batch_op.add_column(sa.Column("known_place_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column("location_accuracy_m", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("location_source", sa.Text(), nullable=False, server_default="unmapped")
        )
        batch_op.add_column(sa.Column("location_key", sa.Text(), nullable=False, server_default=""))
        batch_op.create_foreign_key(
            "fk_incident_statistics_known_place_id", "known_places", ["known_place_id"], ["id"], ondelete="SET NULL"
        )

    bind = op.get_bind()
    known_places = bind.execute(sa.text("SELECT id, name, latitude, longitude FROM known_places WHERE is_active = true")).mappings()
    for place in known_places:
        normalized_name = " ".join(place["name"].strip().lower().split())
        bind.execute(
            sa.text(
                "UPDATE incident_statistics SET known_place_id = :id, latitude = :latitude, longitude = :longitude, "
                "location_source = 'known_place', location_key = :location_key "
                "WHERE normalized_place = :normalized_place"
            ),
            {
                "id": place["id"], "latitude": place["latitude"], "longitude": place["longitude"],
                "location_key": f"known-place:{place['id']}", "normalized_place": normalized_name,
            },
        )
    bind.execute(
        sa.text(
            "UPDATE incident_statistics SET location_key = 'place:' || normalized_place "
            "WHERE location_key = ''"
        )
    )

    with op.batch_alter_table("incident_statistics") as batch_op:
        batch_op.drop_constraint("uq_incident_stats_company_place_type", type_="unique")
        batch_op.create_unique_constraint(
            "uq_incident_stats_company_location_type", ["company_id", "location_key", "type"]
        )
        batch_op.create_check_constraint(
            "ck_incident_statistics_location_source",
            "location_source IN ('gps', 'known_place', 'unmapped')",
        )
        batch_op.create_index("ix_incident_statistics_known_place_id", ["known_place_id"])
        batch_op.create_index("ix_incident_statistics_location_key", ["location_key"])


def downgrade() -> None:
    with op.batch_alter_table("incident_statistics") as batch_op:
        batch_op.drop_index("ix_incident_statistics_location_key")
        batch_op.drop_index("ix_incident_statistics_known_place_id")
        batch_op.drop_constraint("ck_incident_statistics_location_source", type_="check")
        batch_op.drop_constraint("uq_incident_stats_company_location_type", type_="unique")
        batch_op.create_unique_constraint(
            "uq_incident_stats_company_place_type", ["company_id", "normalized_place", "type"]
        )
        batch_op.drop_constraint("fk_incident_statistics_known_place_id", type_="foreignkey")
        batch_op.drop_column("location_key")
        batch_op.drop_column("location_source")
        batch_op.drop_column("location_accuracy_m")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.drop_column("known_place_id")
