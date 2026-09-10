"""Constructores de datos para los tests de la API."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from ygg_core.domain.participant import ParticipantStats

from app.db.models.player import Player, RoleEnum
from app.db.models.user import User


def unique(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def make_stats(match_id: str, puuid: str, **overrides) -> ParticipantStats:
    values = dict(
        match_id=match_id,
        # Anterior a la temporada 26: la caché no exige datos de Role Quest.
        creation_time=datetime(2025, 6, 1, 12, tzinfo=timezone.utc),
        duration=1800,
        puuid=puuid,
        participant_id=1,
        team_id=100,
        player_role="MID",
        champion="Ahri",
        win=True,
        kills=5,
        deaths=2,
        assists=7,
        gold_diff_14=150,
        death_events=[{"x": 7400, "y": 7600, "time": 300, "assistingParticipantIds": []}],
        timeline_enriched=True,
    )
    values.update(overrides)
    return ParticipantStats(**values)


def create_user(db: Session) -> User:
    user = User(email=f"{unique('u')}@example.com", username=unique("user"), hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_player(
    db: Session, *, user: User | None = None, puuid: str | None = None, role: RoleEnum = RoleEnum.MID
) -> Player:
    owner = user or create_user(db)
    player = Player(
        user_id=owner.id,
        puuid=puuid or unique("puuid"),
        game_name=unique("P"),
        tag_line="EUW",
        region="euw",
        role=role,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player
