from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.db.models.user import User
from app.db.session import get_db

# auto_error=False: with no header we answer 401 (unauthenticated), not 403 (no permission).
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Protects the authenticated endpoints: validates the access token and returns the active user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized

    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise unauthorized
    return user


PREMIUM_ROLES = ("premium", "admin")


def is_premium(user: User) -> bool:
    return user.role in PREMIUM_ROLES


async def require_premium(current_user: User = Depends(get_current_user)) -> User:
    """Requires an account with replay access (or admin). The detail is fixed so that the web knows to show the padlock."""
    if not is_premium(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="premium_required")
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requires the authenticated user to have the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permissions required.",
        )
    return current_user
