"""Downloads again the matches stored with an earlier timeline computation.

Each match is two requests to Riot (match and timeline) and the client's rate limiter
spreads the quota: with a development key about 35 matches come out every
two minutes. It can be cut and relaunched; it only requests the ones that are still out of date.

    python scripts/refresh_timelines.py [--limit N]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.service.timeline_refresh import outdated_participants, refresh_outdated_timelines  # noqa: E402


def _progress(done: int, total: int, updated: int) -> None:
    if done % 10 == 0 or done == total:
        print(f"{done}/{total} matches checked, {updated} updated", flush=True)


async def main(limit: int | None) -> None:
    async with SessionLocal() as db:
        pending = len(await outdated_participants(db, limit=limit))
        print(f"{pending} matches stored with an earlier timeline computation.", flush=True)
        if pending:
            updated = await refresh_outdated_timelines(db, limit=limit, on_progress=_progress)
            print(f"Done: {updated} of {pending} matches updated.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Downloads again the matches with an earlier timeline.")
    parser.add_argument("--limit", type=int, help="maximum number of matches to download")
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main(parser.parse_args().limit))
