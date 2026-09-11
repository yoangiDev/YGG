"""Datos de la demo pública: una cuenta de solo lectura con jugadores y análisis.

Los jugadores y las partidas son sintéticos (nombres, puuid e ids de partida con
prefijo DEMO) pero tienen exactamente la forma que produce ygg-core al analizar
partidas reales. El dashboard, el radar y el mapa de calor de la demo se calculan
con el mismo código que en producción; lo único inventado son los números.

El generador es determinista (semilla fija): dos siembras dan los mismos datos.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import DeathEvent, ParticipantStats, WardEvent
from ygg_core.riot.routing import platform_from_region

from app.auth.passwords import hash_password, validate_password_policy
from app.crud.participants import add_history_entries, link_snapshot, upsert_participants
from app.db.models.player import Player, RoleEnum
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.rank_cutoff import RankCutoff
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.db.models.user import User
from app.service.league_service import upsert_cutoffs

SEED = 2026
MAP_SIZE = 14_870
LANE_PHASE_END_SEC = 14 * 60


@dataclass(frozen=True, slots=True)
class DemoPlayer:
    slug: str
    game_name: str
    region: str
    role: RoleEnum
    tier: str
    rank: str
    lp: int
    wins: int
    losses: int
    profile_icon_id: int
    champions: tuple[str, ...]
    skill: float  # 0-1: desplaza todas las métricas


DEMO_PLAYERS: tuple[DemoPlayer, ...] = (
    # Iconos de invocador clásicos (0-28): existen en todas las versiones de Data Dragon.
    DemoPlayer("mid", "Demo Mid", "euw", RoleEnum.MID, "MASTER", "I", 214, 131, 108, 7,
               ("Ahri", "Orianna", "Syndra", "Azir", "Viktor"), 0.78),
    DemoPlayer("jungle", "Demo Jungle", "euw", RoleEnum.JUNGLE, "DIAMOND", "II", 57, 88, 81, 23,
               ("LeeSin", "Viego", "Sejuani", "Vi", "Nidalee"), 0.6),
    DemoPlayer("bot", "Demo ADC", "kr", RoleEnum.BOTTOM, "EMERALD", "I", 76, 64, 66, 28,
               ("Jinx", "Kaisa", "Ezreal", "Varus", "Ashe"), 0.45),
)

# Zonas donde suele morir cada rol (coordenadas de juego), para un mapa de calor verosímil.
_HOTSPOTS: dict[RoleEnum, tuple[tuple[int, int], ...]] = {
    RoleEnum.MID: ((7400, 7400), (6000, 6100), (8900, 8800), (9800, 4400)),
    RoleEnum.JUNGLE: ((3800, 7800), (7000, 10300), (10900, 7100), (9800, 4400), (5000, 10500)),
    RoleEnum.BOTTOM: ((12500, 2200), (13500, 4000), (10500, 1500), (9800, 4400)),
}
_BUILDS: dict[RoleEnum, tuple[tuple[int, ...], int, int, int, int]] = {
    # (objetos, rune principal, árbol secundario, hechizo 1, hechizo 2)
    RoleEnum.MID: ((6655, 3020, 3089, 4645, 3135, 3157, 3363), 8112, 8200, 4, 14),
    RoleEnum.JUNGLE: ((6692, 3111, 3071, 3053, 6333, 3026, 3364), 8010, 8400, 4, 11),
    RoleEnum.BOTTOM: ((6672, 3006, 3031, 3094, 3036, 3072, 3363), 8008, 8300, 4, 7),
}
_BASE_CS_PER_MIN = {RoleEnum.JUNGLE: 5.4, RoleEnum.SUPPORT: 1.3}
_BASE_VISION_PER_MIN = {RoleEnum.JUNGLE: 0.9, RoleEnum.SUPPORT: 1.9}
# Cortes de LP de ejemplo, solo si la plataforma aún no tiene datos reales.
_CUTOFFS = {"euw1": (348, 811), "kr": (612, 1034)}


@dataclass(frozen=True, slots=True)
class SeedResult:
    user_id: int
    players: int
    snapshots: int
    matches: int


def _clamp(value: float) -> int:
    return max(0, min(MAP_SIZE, round(value)))


def _death(rng: random.Random, role: RoleEnum, duration: int) -> DeathEvent:
    x, y = rng.choice(_HOTSPOTS[role])
    return {
        "x": _clamp(rng.gauss(x, 650)),
        "y": _clamp(rng.gauss(y, 650)),
        "time": rng.randint(150, duration - 30),
        "assistingParticipantIds": rng.sample(range(6, 11), k=rng.randint(0, 2)),
    }


def _ward(rng: random.Random, duration: int) -> WardEvent:
    x, y = rng.choice(((9800, 4400), (5000, 10500), (7400, 7400), (4800, 8600), (10000, 6400)))
    return {
        "x": _clamp(rng.gauss(x, 900)),
        "y": _clamp(rng.gauss(y, 900)),
        "time": rng.randint(90, duration),
        "type": rng.choice(("YELLOW_TRINKET", "YELLOW_TRINKET", "CONTROL_WARD", "BLUE_TRINKET")),
    }


def make_participant(
    rng: random.Random, demo: DemoPlayer, match_id: str, played_at: datetime, trend: float
) -> ParticipantStats:
    """Una partida verosímil de `demo`. `trend` desplaza el nivel (períodos peores o mejores)."""
    skill = min(1.0, max(0.0, demo.skill + trend + rng.uniform(-0.25, 0.25)))
    win = rng.random() < 0.36 + skill * 0.28
    duration = rng.randint(1380, 2280)
    minutes = duration / 60

    kills = max(0, round(rng.gauss(3 + skill * 5 + (1.5 if win else 0), 2)))
    deaths = max(0, round(rng.gauss(5.2 - skill * 2.6 + (0 if win else 1), 1.6)))
    assists = max(0, round(rng.gauss(5 + skill * 3 + (2 if win else 0), 2.5)))
    team_kills = max(kills + assists, 1, round((kills + assists) / rng.uniform(0.45, 0.78)))

    cs_per_min = max(0.5, rng.gauss(_BASE_CS_PER_MIN.get(demo.role, 6.8) + skill * 1.6, 0.5))
    gold_diff_14 = round(rng.gauss(-250 + skill * 700 + (250 if win else -150), 450))
    cs_diff_14 = round(rng.gauss(skill * 18 - 6, 8))
    death_events = sorted((_death(rng, demo.role, duration) for _ in range(deaths)), key=lambda d: d["time"])
    items, primary_rune, secondary_tree, spell1, spell2 = _BUILDS[demo.role]
    champion = rng.choices(demo.champions, weights=(5, 4, 3, 2, 2))[0]

    return ParticipantStats(
        match_id=match_id,
        creation_time=played_at,
        duration=duration,
        game_version="16.10.1",
        puuid=f"demo-{demo.slug}",
        participant_id=3,
        team_id=rng.choice((100, 200)),
        player_role=demo.role.value,
        champion=champion,
        win=win,
        kills=kills,
        deaths=deaths,
        assists=assists,
        kill_participation=round(min(100.0, (kills + assists) / team_kills * 100), 1),
        vision=round(minutes * max(0.2, rng.gauss(_BASE_VISION_PER_MIN.get(demo.role, 0.6) + skill * 0.3, 0.12))),
        damage=round(minutes * max(150.0, rng.gauss(650 + skill * 350, 120))),
        gold=round(minutes * max(200.0, rng.gauss(360 + skill * 90 + (25 if win else 0), 25))),
        total_cs=round(cs_per_min * minutes),
        damage_share=round(rng.uniform(17, 31) + skill * 3, 1),
        first_dragon=rng.random() < (0.62 if win else 0.35),
        void_grubs=rng.random() < (0.58 if win else 0.33),
        herald=rng.random() < (0.55 if win else 0.3),
        summoner1_id=spell1,
        summoner2_id=spell2,
        item0=items[0],
        item1=items[1],
        item2=items[2],
        item3=items[3] if rng.random() < 0.85 else 0,
        item4=items[4] if rng.random() < 0.6 else 0,
        item5=items[5] if rng.random() < 0.35 else 0,
        item6=items[6],
        primary_rune=primary_rune,
        secondary_tree=secondary_tree,
        solo_kills=rng.randint(0, 3),
        damage_structures=round(minutes * rng.uniform(40, 160)),
        gold_share=round(rng.uniform(18, 26), 1),
        enemy_jg_monsters=rng.randint(4, 14) if demo.role is RoleEnum.JUNGLE else rng.randint(0, 2),
        control_wards=rng.randint(1, 5),
        roaming_proactivity=rng.randint(0, 4),
        objective_vision_score=rng.randint(2, 12),
        early_gank_deaths=sum(
            1 for d in death_events if d["time"] < LANE_PHASE_END_SEC and d["assistingParticipantIds"]
        ),
        cs_8=round(cs_per_min * 8 * 0.9),
        cs_14=round(cs_per_min * 14 * 0.95),
        cs_25=round(cs_per_min * 25),
        cs_diff_8=round(cs_diff_14 * 0.5),
        cs_diff_14=cs_diff_14,
        cs_diff_25=round(cs_diff_14 * 1.5),
        gold_diff_8=round(gold_diff_14 * 0.45),
        gold_diff_14=gold_diff_14,
        gold_diff_25=round(gold_diff_14 * 1.6),
        xp_diff_8=round(rng.gauss(skill * 300 - 100, 150)),
        xp_diff_14=round(rng.gauss(skill * 600 - 200, 300)),
        death_events=death_events,
        ward_events=[_ward(rng, duration) for _ in range(rng.randint(4, 12))],
        dragon_setups=[],
        fullclear_time=rng.randint(190, 230) if demo.role is RoleEnum.JUNGLE else None,
        timeline_enriched=True,
    )


async def _free_username(db: AsyncSession, base: str) -> str:
    candidate, suffix = base, 1
    while await db.scalar(select(User.id).where(User.username == candidate)) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


async def _reset_players(db: AsyncSession, user_id: int) -> None:
    """Borra los jugadores de la cuenta demo y lo que cuelga de ellos. Las partidas se reutilizan."""
    player_ids = select(Player.id).where(Player.user_id == user_id)
    snapshot_ids = select(Snapshot.id).where(Snapshot.player_id.in_(player_ids))
    await db.execute(delete(SnapshotParticipant).where(SnapshotParticipant.snapshot_id.in_(snapshot_ids)))
    await db.execute(delete(Snapshot).where(Snapshot.player_id.in_(player_ids)))
    await db.execute(delete(PlayerHistoryEntry).where(PlayerHistoryEntry.player_id.in_(player_ids)))
    await db.execute(delete(Player).where(Player.user_id == user_id))


async def seed_demo(
    db: AsyncSession, *, email: str, password: str, now: datetime | None = None
) -> SeedResult:
    """Crea (o recrea) la cuenta demo con sus jugadores, historial y dos snapshots por jugador."""
    validate_password_policy(password)
    now = now or datetime.now(timezone.utc)
    rng = random.Random(SEED)

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, username=await _free_username(db, "demo"), hashed_password="")
        db.add(user)
    user.hashed_password = hash_password(password)
    user.role = "user"
    user.is_active = True
    await db.flush()
    await _reset_players(db, user.id)

    snapshots = matches = 0
    # (inicio, fin, descripción, desplazamiento del nivel, partidas)
    periods = (
        (now - timedelta(days=60), now - timedelta(days=30), "Previous month", -0.12, 22),
        (now - timedelta(days=30), now - timedelta(hours=2), "Last 30 days", 0.0, 26),
    )
    for demo in DEMO_PLAYERS:
        player = Player(
            user_id=user.id,
            puuid=f"demo-{demo.slug}",
            game_name=demo.game_name,
            tag_line="DEMO",
            region=demo.region,
            nickname="Demo",
            role=demo.role,
            notes="Seeded demo player: numbers are synthetic, the analysis pipeline is the real one.",
            tier=demo.tier,
            rank=demo.rank,
            lp=demo.lp,
            wins=demo.wins,
            losses=demo.losses,
            profile_icon_id=demo.profile_icon_id,
            match_history_cached_at=now,
        )
        db.add(player)
        await db.flush()

        history: list[int] = []
        for index, (start, end, description, trend, games) in enumerate(periods):
            span = end - start
            participants = [
                make_participant(
                    rng,
                    demo,
                    f"DEMO_{demo.slug.upper()}_{index}_{game:02d}",
                    start + span * ((game + rng.random()) / games),
                    trend,
                )
                for game in range(games)
            ]
            ids = await upsert_participants(db, participants)
            snapshot = Snapshot(player_id=player.id, date_from=start, date_to=end, description=description, notes="")
            db.add(snapshot)
            await db.flush()
            await link_snapshot(db, snapshot.id, ids.values())
            history.extend(ids.values())
            snapshots += 1
            matches += len(participants)
        await add_history_entries(db, player.id, history)

    await db.commit()

    for platform in sorted({platform_from_region(demo.region) for demo in DEMO_PLAYERS}):
        if platform in _CUTOFFS and await db.get(RankCutoff, platform) is None:
            await upsert_cutoffs(db, platform, *_CUTOFFS[platform])

    return SeedResult(user_id=user.id, players=len(DEMO_PLAYERS), snapshots=snapshots, matches=matches)
