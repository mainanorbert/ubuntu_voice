"""Emit deterministic progress for the GPS place-name backfill."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    job_dir = Path(sys.argv[1])
    checkpoint = json.loads((job_dir / "checkpoint.json").read_text(encoding="utf-8"))
    total = int(checkpoint["total"])
    processed = int(checkpoint["processed"])
    started_at = datetime.fromisoformat(checkpoint["started_at"])
    elapsed = max(time.time() - started_at.timestamp(), 0.001)
    rate = processed / elapsed
    remaining = max(total - processed, 0)
    eta = remaining / rate if rate else None
    percent = (processed / total * 100) if total else 100.0
    eta_text = "complete" if eta is None else f"{eta:.1f}s"
    line = (
        f"GPS place-name backfill — {percent:.1f}% — ETA {eta_text}; "
        f"coordinates {processed}/{total}, rows updated {checkpoint['updated_rows']}, "
        f"lookup failures {checkpoint['lookup_failures']}"
    )
    print(line)
    with (job_dir / "progress.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(UTC).isoformat()} {line}\n")


if __name__ == "__main__":
    main()
