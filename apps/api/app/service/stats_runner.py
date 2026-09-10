import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from ygg_core.domain.roles import role_filter_for_player

from app.crud.participants import known_participants, link_snapshot, upsert_participants
from app.db.models.job import Job
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.service.riot import create_secure_session, participant_from_row, player_ref, riot_client

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
        self._job: Job | None = None

    def _get_job(self) -> Job | None:
        if self._job is None and self._job_id:
            self._job = self._db.get(Job, self._job_id)
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
    Analiza un período de un jugador: ygg-core descarga y calcula, aquí se persiste.
    """
    progress = _ProgressBatcher(db, job_id)
    client = riot_client(player.region)
    role_value = role_filter_for_player(player.role.value if player.role else None)

    async with create_secure_session() as session:
        match_ids = await client.fetch_match_ids(session, player.puuid, date_from, date_to)

        # Solo las filas de ESTE jugador sirven de caché: reutilizar la de otro
        # participante de la misma partida era el bug P1.
        known_rows = known_participants(db, player.puuid, match_ids)
        known = {match_id: participant_from_row(row) for match_id, row in known_rows.items()}
        cached_count = sum(1 for row in known_rows.values() if row.timeline_enriched)
        if cached_count:
            logger.info(
                "[%s] %d/%d matches will be reused from DB (timeline_enriched).",
                player.game_name, cached_count, len(match_ids),
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
            known=known,
            match_ids=match_ids,
        )

    progress.flush()

    if not participants:
        raise ValueError("No matches found for the selected period and role.")

    # Las que venían de la caché ya están guardadas tal cual: solo se escriben las nuevas.
    fresh = [p for p in participants if known.get(p.match_id) is not p]
    ids = {(row.match_id, row.puuid): row.id for row in known_rows.values()}
    ids.update(upsert_participants(db, fresh))
    progress.update(95)

    snapshot = Snapshot(
        player_id=player.id,
        date_from=datetime.fromtimestamp(date_from, tz=timezone.utc),
        date_to=datetime.fromtimestamp(date_to, tz=timezone.utc),
        description=description,
    )
    db.add(snapshot)
    db.flush()
    link_snapshot(db, snapshot.id, (ids[(p.match_id, p.puuid)] for p in participants))

    db.commit()
    db.refresh(snapshot)

    if job_id:
        job = db.get(Job, job_id)
        if job:
            job.progress = 100
            db.commit()

    logger.info(
        "Snapshot %d created with %d matches for player %s#%s.",
        snapshot.id, len(participants), player.game_name, player.tag_line,
    )
    return snapshot.id
