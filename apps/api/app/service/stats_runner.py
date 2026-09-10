import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ygg_core.domain.roles import role_filter_for_player

from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.job import Job
from app.service.riot import (
    copy_timeline_fields,
    create_secure_session,
    match_to_participant,
    participant_to_match,
    player_ref,
    riot_client,
)

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
    Orquesta el flujo completo de extracción de estadísticas para un jugador:
    ygg-core descarga y calcula; aquí solo se persiste.
    """
    progress = _ProgressBatcher(db, job_id)
    client = riot_client(player.region)
    role_value = role_filter_for_player(player.role.value if player.role else None)

    async with create_secure_session() as session:
        match_ids = await client.fetch_match_ids(session, player.puuid, date_from, date_to)

        existing_rows: dict[str, Match] = {}
        if match_ids:
            rows = db.query(Match).filter(Match.match_id.in_(match_ids)).all()
            existing_rows = {m.match_id: m for m in rows}
            cached_count = sum(1 for m in rows if m.timeline_enriched)
            if cached_count:
                logger.info(
                    f"[{player.game_name}] {cached_count}/{len(match_ids)} matches "
                    "will be reused from DB (timeline_enriched)."
                )

        def _download_progress(completed: int, total: int):
            if total > 0:
                progress.update(int((completed / total) * 90))

        participants = await client.fetch_participants(
            session,
            player_ref(player),
            start_t=date_from,
            end_t=date_to,
            role_filter=role_value,
            on_progress=_download_progress,
            known={mid: match_to_participant(row) for mid, row in existing_rows.items()},
            match_ids=match_ids,
        )

    progress.flush()

    if not participants:
        raise ValueError("No matches found for the selected period and role.")

    snapshot = Snapshot(
        player_id=player.id,
        date_from=datetime.fromtimestamp(date_from, tz=timezone.utc),
        date_to=datetime.fromtimestamp(date_to, tz=timezone.utc),
        description=description,
    )
    db.add(snapshot)
    db.flush()

    total = len(participants)
    links: list[MatchSnapshot] = []

    for i, stats in enumerate(participants):
        existing_match = existing_rows.get(stats.match_id)

        if existing_match:
            copy_timeline_fields(existing_match, stats)
            target = existing_match
        else:
            match = participant_to_match(stats)
            try:
                sp = db.begin_nested()
                db.add(match)
                db.flush()
                target = match
            except IntegrityError:
                sp.rollback()
                existing_match = (
                    db.query(Match).filter(Match.match_id == stats.match_id).first()
                )
                if not existing_match:
                    continue
                copy_timeline_fields(existing_match, stats)
                target = existing_match

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
        f"Snapshot {snapshot.id} created with {total} matches "
        f"for player {player.game_name}#{player.tag_line}."
    )

    return snapshot.id
