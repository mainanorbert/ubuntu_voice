"""Backfill readable locality names for GPS statistic rows."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import update

from src.core.config import Settings
from src.core.database import create_database_engine, create_session_factory
from src.models import IncidentStatistic
from src.services.location_geocoding import APPROXIMATE_LOCATION_LABEL, reverse_geocode_short_place_name

MAX_SNAPSHOT_ROWS = 100_000
MAX_SNAPSHOT_BYTES = 100 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Apply updates after creating the snapshot.")
    return parser.parse_args()


def write_checkpoint(path: Path, **values: object) -> None:
    path.write_text(json.dumps(values, indent=2, default=str) + "\n", encoding="utf-8")


def row_snapshot(row: IncidentStatistic) -> dict[str, object]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "place": row.place,
        "normalized_place": row.normalized_place,
        "latitude": str(row.latitude) if row.latitude is not None else None,
        "longitude": str(row.longitude) if row.longitude is not None else None,
        "location_accuracy_m": row.location_accuracy_m,
        "location_source": row.location_source,
        "location_key": row.location_key,
        "description": row.description,
        "type": row.type,
        "total_count": row.total_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def main() -> None:
    args = parse_args()
    args.job_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(_env_file=".env")
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    checkpoint_path = args.job_dir / "checkpoint.json"
    snapshot_path = args.job_dir / "before.jsonl"
    report_path = args.job_dir / "report.md"
    csv_path = args.job_dir / "before_after.csv"
    started_at = time.time()

    with factory() as session:
        rows = (
            session.query(IncidentStatistic)
            .filter(
                IncidentStatistic.location_source == "gps",
                IncidentStatistic.place == APPROXIMATE_LOCATION_LABEL,
                IncidentStatistic.latitude.is_not(None),
                IncidentStatistic.longitude.is_not(None),
            )
            .order_by(IncidentStatistic.id)
            .all()
        )
        snapshot = [row_snapshot(row) for row in rows]
        snapshot_bytes = sum(len(json.dumps(row).encode("utf-8")) + 1 for row in snapshot)
        if len(snapshot) > MAX_SNAPSHOT_ROWS or snapshot_bytes > MAX_SNAPSHOT_BYTES:
            raise RuntimeError(
                f"Snapshot exceeds safety limit: rows={len(snapshot)}, bytes={snapshot_bytes}. "
                "Obtain permission before continuing."
            )
        snapshot_path.write_text("".join(json.dumps(row) + "\n" for row in snapshot), encoding="utf-8")

        unique_coordinates = sorted({(row["latitude"], row["longitude"]) for row in snapshot})
        write_checkpoint(
            checkpoint_path,
            event="GPS place-name backfill",
            started_at=datetime.now(UTC).isoformat(),
            total=len(unique_coordinates),
            processed=0,
            updated_rows=0,
            lookup_failures=0,
            dry_run=not args.execute,
        )
        if not args.execute:
            report_path.write_text(
                f"# GPS place-name backfill preview\n\nAffected rows: {len(snapshot)}\n\n"
                f"Unique coordinates: {len(unique_coordinates)}\n\nSnapshot: `{snapshot_path}`\n",
                encoding="utf-8",
            )
            return

        api_key = settings.google_maps_api_key
        if not api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured in the backend environment.")

        before_after: list[dict[str, object]] = []
        updated_rows = 0
        lookup_failures = 0
        for index, (latitude_text, longitude_text) in enumerate(unique_coordinates, start=1):
            latitude = Decimal(latitude_text)
            longitude = Decimal(longitude_text)
            place_name = asyncio.run(
                reverse_geocode_short_place_name(
                    api_key=api_key,
                    latitude=latitude,
                    longitude=longitude,
                )
            )
            target_ids = [
                row["id"]
                for row in snapshot
                if row["latitude"] == latitude_text and row["longitude"] == longitude_text
            ]
            if place_name:
                result = session.execute(
                    update(IncidentStatistic)
                    .where(
                        IncidentStatistic.id.in_(target_ids),
                        IncidentStatistic.place == APPROXIMATE_LOCATION_LABEL,
                    )
                    .values(place=place_name)
                )
                session.commit()
                updated_rows += result.rowcount or 0
            else:
                lookup_failures += 1
            for row in snapshot:
                if row["id"] in target_ids:
                    before_after.append(
                        {
                            "id": row["id"],
                            "company_id": row["company_id"],
                            "location_key": row["location_key"],
                            "latitude": row["latitude"],
                            "longitude": row["longitude"],
                            "before_place": row["place"],
                            "after_place": place_name or row["place"],
                            "type": row["type"],
                            "status": "updated" if place_name else "skipped_lookup_failed",
                        }
                    )
            write_checkpoint(
                checkpoint_path,
                event="GPS place-name backfill",
                started_at=datetime.fromtimestamp(started_at, UTC).isoformat(),
                total=len(unique_coordinates),
                processed=index,
                updated_rows=updated_rows,
                lookup_failures=lookup_failures,
                dry_run=False,
            )

        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=before_after[0].keys() if before_after else ["id"])
            writer.writeheader()
            writer.writerows(before_after)
        examples = before_after[:10]
        report_path.write_text(
            "# GPS place-name backfill report\n\n"
            "## Verdict\n\n"
            f"Completed: `{updated_rows}` rows updated across `{len(unique_coordinates)}` unique coordinates.\n\n"
            f"Lookup failures: `{lookup_failures}`. Failed lookups retained the fallback label.\n\n"
            "## Examples\n\n"
            "| Before | After | Type | Status |\n|---|---|---|---|\n"
            + "\n".join(
                f"| {item['before_place']} | {item['after_place']} | {item['type']} | {item['status']} |"
                for item in examples
            )
            + f"\n\nFull before/after CSV: `{csv_path}`\nSnapshot: `{snapshot_path}`\n",
            encoding="utf-8",
        )
    engine.dispose()


if __name__ == "__main__":
    main()
