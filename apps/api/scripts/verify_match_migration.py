"""Comprueba los conteos de la migración match_data → match_participants.

Pensado para ejecutarse en producción entre la copia y el borrado:

    alembic upgrade 4d2e9f6a8b31        # crea tablas y copia datos
    python scripts/verify_match_migration.py
    alembic upgrade head                # verifica de nuevo y borra match_data

La propia migración de borrado repite estas comprobaciones y aborta si no
cuadran; este script sirve para verlas antes y decidir con calma.
Solo necesita DATABASE_URL.
"""

import os
import sys

from sqlalchemy import create_engine, text

CHECKS = (
    (
        "Enlaces de snapshot (antiguos = copiados + no resueltos)",
        "SELECT count(*) FROM match_snapshots",
        "SELECT (SELECT count(*) FROM snapshot_participants)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'snapshot')",
    ),
    (
        "Enlaces de historial (antiguos = copiados + no resueltos)",
        "SELECT count(*) FROM player_match_history",
        "SELECT (SELECT count(*) FROM player_history_entries)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'history')",
    ),
    (
        "Filas enlazadas de match_data = participantes",
        "SELECT count(*) FROM match_data md WHERE"
        " EXISTS (SELECT 1 FROM match_snapshots ms WHERE ms.match_id = md.id)"
        " OR EXISTS (SELECT 1 FROM player_match_history h WHERE h.match_id = md.id)",
        "SELECT count(*) FROM match_participants",
    ),
    (
        "Partidas distintas = filas en matches",
        "SELECT count(DISTINCT match_id) FROM match_participants",
        "SELECT count(*) FROM matches",
    ),
)

INFO = (
    ("Filas huérfanas de match_data (no se copian)",
     "SELECT count(*) FROM match_data md WHERE"
     " NOT EXISTS (SELECT 1 FROM match_snapshots ms WHERE ms.match_id = md.id)"
     " AND NOT EXISTS (SELECT 1 FROM player_match_history h WHERE h.match_id = md.id)"),
    ("Enlaces no resueltos (a recalcular con repair_legacy_links.py)",
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
            print(f"[{'OK ' if ok else 'MAL'}] {label}: {old} → {new}")
        for label, sql in INFO:
            print(f"[INFO] {label}: {connection.execute(text(sql)).scalar_one()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
