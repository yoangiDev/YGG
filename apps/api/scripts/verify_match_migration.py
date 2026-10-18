"""Checks the counts of the match_data → match_participants migration.

Meant to be run in production between the copy and the drop:

    alembic upgrade 4d2e9f6a8b31        # creates tables and copies data
    python scripts/verify_match_migration.py
    alembic upgrade head                # verifies again and drops match_data

The drop migration itself repeats these checks and aborts if they don't
add up; this script is for seeing them beforehand and deciding calmly.
It only needs DATABASE_URL.
"""

import os
import sys

from sqlalchemy import create_engine, text

CHECKS = (
    (
        "Snapshot links (old = copied + unresolved)",
        "SELECT count(*) FROM match_snapshots",
        "SELECT (SELECT count(*) FROM snapshot_participants)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'snapshot')",
    ),
    (
        "History links (old = copied + unresolved)",
        "SELECT count(*) FROM player_match_history",
        "SELECT (SELECT count(*) FROM player_history_entries)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'history')",
    ),
    (
        "Rows linked in match_data = participants",
        "SELECT count(*) FROM match_data md WHERE"
        " EXISTS (SELECT 1 FROM match_snapshots ms WHERE ms.match_id = md.id)"
        " OR EXISTS (SELECT 1 FROM player_match_history h WHERE h.match_id = md.id)",
        "SELECT count(*) FROM match_participants",
    ),
    (
        "Distinct games = rows in matches",
        "SELECT count(DISTINCT match_id) FROM match_participants",
        "SELECT count(*) FROM matches",
    ),
)

INFO = (
    ("Orphan match_data rows (not copied)",
     "SELECT count(*) FROM match_data md WHERE"
     " NOT EXISTS (SELECT 1 FROM match_snapshots ms WHERE ms.match_id = md.id)"
     " AND NOT EXISTS (SELECT 1 FROM player_match_history h WHERE h.match_id = md.id)"),
    ("Unresolved links (to recompute with repair_legacy_links.py)",
     "SELECT count(*) FROM legacy_unresolved_links"),
)


def main() -> int:
    engine = create_engine(os.environ["DATABASE_URL"])
    failed = False
    with engine.connect() as connection:
        for label, old_sql, new_sql in CHECKS:
            old = connection.execute(text(old_sql)).scalar_one()
            new = connection.execute(text(new_sql)).scalar_one()
            ok = old == new
            failed |= not ok
            print(f"[{'OK ' if ok else 'BAD'}] {label}: {old} → {new}")
        for label, sql in INFO:
            print(f"[INFO] {label}: {connection.execute(text(sql)).scalar_one()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
