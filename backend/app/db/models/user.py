from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    email               = Column(String(255), unique=True, nullable=False, index=True)
    username            = Column(String(50), unique=True, nullable=False)
    hashed_password     = Column(String(255), nullable=False)
    role                = Column(String(20), nullable=False, default='user', server_default='user')
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    avatar_url          = Column(String(500), nullable=True)

    # ── Relaciones ─────────────────────────────────────────────────────────────
    players = relationship(
        "Player",
        back_populates="owner",
        cascade="all, delete-orphan"  # Si se borra el user, se borran sus jugadores
    )