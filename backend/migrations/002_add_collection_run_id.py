"""
Migration: add `collection_run_id` to price_snapshots.

WHY A SCRIPT AND NOT create_all():
    Base.metadata.create_all() only CREATEs missing tables. It will not add
    a column to a table that already exists, so an existing
    market_pulse.db keeps its old schema silently and every insert then
    fails on the unknown column.

WHY THIS ONE IS EASY:
    Unlike the items rebuild, this is a pure column addition with no
    constraint change - SQLite's ALTER TABLE ADD COLUMN handles it
    directly, no table rebuild needed.

BACKFILL:
    Existing rows are grouped into runs by clustering collected_at: any
    gap larger than GAP_SECONDS starts a new run. That works because a
    sweep writes all its rows within seconds while runs are minutes apart.

    This is a HEURISTIC, and it is only trustworthy for the old
    single-category data where a sweep took under a second. It is exactly
    the guesswork the new column exists to eliminate - which is the
    argument for adding the column before the Pi starts writing slow,
    minute-long sweeps rather than after.

Run from backend/, with the app stopped:
    python migrations/002_add_collection_run_id.py
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "market_pulse.db"

# Rows more than this far apart are treated as separate runs. Comfortably
# larger than any single old sweep, comfortably smaller than the 10-minute
# collection interval those rows were written at.
GAP_SECONDS = 120


def already_migrated(con: sqlite3.Connection) -> bool:
    columns = {row[1] for row in con.execute("PRAGMA table_info(price_snapshots)")}
    return "collection_run_id" in columns


def backfill(con: sqlite3.Connection) -> int:
    """Group existing rows into runs by clustering their timestamps."""
    rows = con.execute(
        "SELECT id, collected_at FROM price_snapshots ORDER BY collected_at, id"
    ).fetchall()
    if not rows:
        return 0

    def parse(value: str) -> datetime:
        # SQLite stores these as text; tolerate both space and 'T' separators.
        return datetime.fromisoformat(str(value).replace(" ", "T").split("+")[0])

    run_count = 0
    current_run = str(uuid.uuid4())
    previous = parse(rows[0][1])
    updates: list[tuple[str, int]] = []

    for row_id, collected_at in rows:
        current = parse(collected_at)
        if (current - previous).total_seconds() > GAP_SECONDS:
            current_run = str(uuid.uuid4())
            run_count += 1
        updates.append((current_run, row_id))
        previous = current

    con.executemany(
        "UPDATE price_snapshots SET collection_run_id = ? WHERE id = ?", updates
    )
    return run_count + 1


def main() -> int:
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} - nothing to migrate. "
              "A fresh database gets the new column automatically on startup.")
        return 0

    con = sqlite3.connect(DB_PATH)
    try:
        if already_migrated(con):
            print("price_snapshots already has collection_run_id - nothing to do.")
            return 0

        backup = DB_PATH.with_suffix(f".pre-002-{datetime.now():%Y%m%d-%H%M%S}.db")
        shutil.copy2(DB_PATH, backup)
        print(f"Backed up to {backup}")

        with con:  # commits on success, rolls back on exception
            con.execute("ALTER TABLE price_snapshots ADD COLUMN collection_run_id VARCHAR(36)")
            runs = backfill(con)
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_price_snapshots_collection_run_id "
                "ON price_snapshots (collection_run_id)"
            )

        total = con.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        unset = con.execute(
            "SELECT COUNT(*) FROM price_snapshots WHERE collection_run_id IS NULL"
        ).fetchone()[0]

        print(f"Added collection_run_id. {total} rows grouped into {runs} runs "
              f"({unset} left null).")
        print("Backfilled ids are inferred from timestamp gaps, not recorded "
              "at collection time - treat them as approximate.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Migration failed, database left unchanged: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
