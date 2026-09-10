import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.roles import role_filter_for_player

from app.crud.participants import known_participants, link_snapshot, upsert_participants
from app.db.models.job import Job
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.session import SessionLocal
from app.service.dashboard_cache import invalidate_dashboards_for_participants
from app.service.riot import create_secure_session, participant_from_row, player_ref, riot_client

logger = logging.getLogger(__name__)


class _ProgressReporter:
    """Escribe jobs.progress como mucho cada `min_interval` segundos.

    El callback de progreso del core es síncrono y llega mientras la sesión del
    análisis espera a Riot: se escribe en segundo plano y con otra sesión, para
    no usar la misma AsyncSession desde dos corutinas.
    """

    def __init__(self, job_id: str | None, *, min_interval: float = 2.0) -> None:
        self._job_id = job_id
        self._min_interval = min_interval
        self._last_write = 0.0
        self._pending: asyncio.Task[None] | None = None

    def report(self, progress: int) -> None:
        if not self._job_id:
            return
        now = time.monotonic()
        if now - self._last_write < self._min_interval:
            return
        if self._pending is not None and not self._pending.done():
            return
        self._last_write = now
        self._pending = asyncio.get_running_loop().create_task(self._write(min(progress, 99)))

    async def _write(self, progress: int) -> None:
        try:
            async with SessionLocal() as session:
                await session.execute(
                    update(Job).where(Job.job_id == self._job_id).values(progress=progress)
                )
                await session.commit()
        except Exception as exc:  # el progreso es informativo: nunca tumba el análisis
            logger.warning("Could not store progress for job %s: %s", self._job_id, exc)

    async def finish(self, progress: int) -> None:
        if not self._job_id:
            return
        if self._pending is not None:
            await self._pending
        await self._write(progress)


async def run_stats_extraction(
    db: AsyncSession,
    player: Player,
    date_from: int,
    date_to: int,
    description: str = "",
    job_id: str | None = None,
) -> int:
    """Analiza un período de un jugador: ygg-core descarga y calcula, aquí se persiste."""
    progress = _ProgressReporter(job_id)
    client = riot_client(player.region)
    role_value = role_filter_for_player(player.role.value if player.role else None)

    async with create_secure_session() as session:
        match_ids = await client.fetch_match_ids(session, player.puuid, date_from, date_to)

        # Solo las filas de ESTE jugador sirven de caché: reutilizar la de otro
        # participante de la misma partida era el bug P1.
        known_rows = await known_participants(db, player.puuid, match_ids)
        known = {match_id: participant_from_row(row) for match_id, row in known_rows.items()}
        cached_count = sum(1 for row in known_rows.values() if row.timeline_enriched)
        if cached_count:
            logger.info(
                "[%s] %d/%d matches will be reused from DB (timeline_enriched).",
                player.game_name, cached_count, len(match_ids),
            )

        def _download_progress(completed: int, total: int) -> None:
            if total > 0:
                progress.report(int((completed / total) * 90))

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

    if not participants:
        raise ValueError("No matches found for the selected period and role.")

    # Las que venían de la caché ya están guardadas tal cual: solo se escriben las nuevas.
    fresh = [p for p in participants if known.get(p.match_id) is not p]
    fresh_ids = await upsert_participants(db, fresh)
    ids = {(row.match_id, row.puuid): row.id for row in known_rows.values()} | fresh_ids

    snapshot = Snapshot(
        player_id=player.id,
        date_from=datetime.fromtimestamp(date_from, tz=timezone.utc),
        date_to=datetime.fromtimestamp(date_to, tz=timezone.utc),
        description=description,
    )
    db.add(snapshot)
    await db.flush()
    await link_snapshot(db, snapshot.id, (ids[(p.match_id, p.puuid)] for p in participants))
    await db.commit()
    await db.refresh(snapshot)

    # Filas re-descargadas pueden pertenecer también a snapshots anteriores.
    await invalidate_dashboards_for_participants(db, fresh_ids.values())
    await progress.finish(100)

    logger.info(
        "Snapshot %d created with %d matches for player %s#%s.",
        snapshot.id, len(participants), player.game_name, player.tag_line,
    )
    return snapshot.id
