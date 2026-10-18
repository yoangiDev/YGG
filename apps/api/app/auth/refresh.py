"""Opaque refresh tokens with rotation and reuse detection."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User


class RefreshError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


async def issue_refresh_token(
    db: AsyncSession,
    user_id: int,
    *,
    family_id: str | None = None,
    user_agent: str | None = None,
) -> tuple[RefreshToken, str]:
    """Creates a token (no commit). Returns the row and the plain value, which only travels in the cookie."""
    token = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4().hex,
        token_hash=_hash(token),
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(row)
    await db.flush()
    return row, token


async def revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def rotate_refresh_token(
    db: AsyncSession, token: str, *, user_agent: str | None = None
) -> tuple[User, RefreshToken, str]:
    """Exchanges a refresh token for a new one of the same family (with commit)."""
    current = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(token)).with_for_update()
    )
    if current is None:
        raise RefreshError("unknown")

    if current.revoked_at is not None:
        # An already rotated token is used again: either it was stolen or it will be. The whole session goes.
        await revoke_family(db, current.family_id)
        await db.commit()
        raise RefreshError("reused")

    if current.expires_at <= _now():
        raise RefreshError("expired")

    user = await db.get(User, current.user_id)
    if user is None or not user.is_active:
        raise RefreshError("inactive")

    new_row, new_token = await issue_refresh_token(
        db, user.id, family_id=current.family_id, user_agent=user_agent
    )
    current.revoked_at = _now()
    current.replaced_by_id = new_row.id
    await db.commit()
    return user, new_row, new_token


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    """Closes the session the token belongs to (with commit). Unknown token: does nothing."""
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if row is not None:
        await revoke_family(db, row.family_id)
        await db.commit()