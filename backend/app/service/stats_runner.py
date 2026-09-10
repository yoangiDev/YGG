import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.job import Job
from app.service.http_client import create_secure_session
from app.service.riot_client import RiotAPIClient, copy_timeline_fields

logger = logging.getLogger(__name__)


class _ProgressBatcher:
    """Throttles job progress DB commits (every N items or min_interval seconds)."""

    def __init__(
        self,
        db: Session,
        job_id: str | None,
        *,
        every_n: int = 5,
        min_interval: float = 2.0,
    ):
        self._db = db
        self._job_id = job_id
        self._every_n = every_n
        self._min_interval = min_interval
        self._last_commit = 0.0
        self._pending = 0
        self._job = None

    def _get_job(self):
        if self._job is None and self._job_id:
            self._job = self._db.query(Job).filter(Job.job_id == self._job_id).first()
        return self._job

    def update(self, progress: int) -> None:
        if not self._job_id:
            return
        job = self._get_job()
        if not job:
            return
        job.progress = min(progress, 99)
        self._pending += 1
        now = time.monotonic()
        if (
            self._pending >= self._every_n
            or (now - self._last_commit) >= self._min_interval
        ):
            self._db.commit()
            self._pending = 0
            self._last_commit = now

    def flush(self) -> None:
        if self._pending and self._job_id:
            self._db.commit()
            self._pending = 0
            self._last_commit = time.monotonic()


async def run_stats_extraction(
    db: Session,
    player: Player,
    date_from: int,
    date_to: int,
    description: str = "",
    job_id: str | None = None,
) -> int:
    """
    Orquesta el flujo completo de extracción de estadísticas para un jugador.
    """
    progress = _ProgressBatcher(db, job_id)

    client = RiotAPIClient(region=player.region.lower())

    async with create_secure_session() as session:
        role_value = player.role.value if player.role else "ALL"
        if role_value == "BOTTOM":
            role_value = "ADC"

        match_ids = await client._fetch_match_ids(
            session, player.puuid, date_from, date_to, max_matches=None
        )

        known_matches: dict[str, Match] = {}
        if match_ids:
            existing_rows = db.query(Match).filter(Match.match_id.in_(match_ids)).all()
            known_matches = {m.match_id: m for m in existing_rows}
            cached_count = sum(
                1 for m in known_matches.values() if m.timeline_enriched
            )
            if cached_count:
                logger.info(
                    f"[{player.game_name}] {cached_count}/{len(match_ids)} matches "
                    "will be reused from DB (timeline_enriched)."
                )

        def _download_progress(completed: int, total: int):
            if total > 0:
                progress.update(int((completed / total) * 90))

        matches: list[Match] = await client.fetch_matches(
            session=session,
            player=player,
            start_t=date_from,
            end_t=date_to,
            role_filter=role_value,
            on_progress=_download_progress,
            known_matches=known_matches,
            match_ids=match_ids,
        )

    progress.flush()

    if not matches:
        raise ValueError("No matches found for the selected period and role.")

    snapshot = Snapshot(
        player_id=player.id,
        date_from=datetime.fromtimestamp(date_from, tz=timezone.utc),
        date_to=datetime.fromtimestamp(date_to, tz=timezone.utc),
        description=description,
    )
    db.add(snapshot)
    db.flush()

    total = len(matches)
    links: list[MatchSnapshot] = []

    for i, match in enumerate(matches):
        existing_match = db.query(Match).filter(Match.match_id == match.match_id).first()

        if existing_match:
            copy_timeline_fields(existing_match, match)
            if match.timeline_enriched:
                existing_match.timeline_enriched = True
            target = existing_match
        else:
            try:
                sp = db.begin_nested()
                db.add(match)
                db.flush()
                target = match
            except IntegrityError:
                sp.rollback()
                existing_match = (
                    db.query(Match).filter(Match.match_id == match.match_id).first()
                )
                if existing_match:
                    copy_timeline_fields(existing_match, match)
                    if match.timeline_enriched:
                        existing_match.timeline_enriched = True
                    target = existing_match
                else:
                    continue

        links.append(MatchSnapshot(snapshot_id=snapshot.id, match_id=target.id))
        progress.update(90 + int(((i + 1) / total) * 9))

    for link in links:
        try:
            sp = db.begin_nested()
            db.add(link)
            sp.commit()
        except IntegrityError:
            sp.rollback()
            logger.warning(
                f"Association link already exists for match_id={link.match_id} "
                f"in snapshot {snapshot.id}"
            )

    db.commit()
    db.refresh(snapshot)
    progress.flush()

    if job_id:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.progress = 100
            db.commit()

    logger.info(
        f"Snapshot {snapshot.id} created with {len(matches)} matches "
        f"for player {player.game_name}#{player.tag_line}."
    )

    return snapshot.id
