from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password, verify_password_or_dummy
from app.auth.refresh import (
    RefreshError,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.core.config import settings
from app.core.rate_limit import client_ip, enforce, rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import DeleteAccount, TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/auth"


def _token_response(user_id: int) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        expires=expires_at,
        path=REFRESH_COOKIE_PATH,
        httponly=True,  # inaccessible from JavaScript: an XSS can't steal it
        secure=settings.secure_cookies,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )


async def _start_session(db: AsyncSession, user: User, request: Request, response: Response) -> TokenResponse:
    row, token = await issue_refresh_token(db, user.id, user_agent=request.headers.get("user-agent"))
    await db.commit()
    _set_refresh_cookie(response, token, row.expires_at)
    return _token_response(user.id)


# ── POST /auth/register ────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", "rate_limit_register_per_hour", 3600))],
)
async def register(user_in: UserRegister, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(User.id).where(User.email == user_in.email)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already registered.")
    if await db.scalar(select(User.id).where(User.username == user_in.username)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This username is already taken.")

    user = User(email=user_in.email, username=user_in.username, hashed_password=hash_password(user_in.password))
    db.add(user)
    await db.flush()
    return await _start_session(db, user, request, response)


# ── POST /auth/login ───────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid credentials"}, 429: {"description": "Too many attempts"}},
)
async def login(credentials: UserLogin, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await enforce("login-ip", client_ip(request), settings.rate_limit_login_per_minute, 60, response)
    await enforce(
        "login-email", credentials.email.lower(), settings.rate_limit_login_per_email_per_hour, 3600, response
    )

    user = await db.scalar(select(User).where(User.email == credentials.email))
    if not verify_password_or_dummy(credentials.password, user.hashed_password if user else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled.")

    return await _start_session(db, user, request, response)


# ── POST /auth/refresh ─────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"description": "Missing, expired, revoked or reused refresh token"}},
    dependencies=[Depends(rate_limit("refresh", "rate_limit_refresh_per_minute", 60))],
)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Exchanges the refresh cookie for a new access token and rotates the cookie."""
    token = request.cookies.get(settings.refresh_cookie_name)
    try:
        if not token:
            raise RefreshError("missing")
        user, row, new_token = await rotate_refresh_token(
            db, token, user_agent=request.headers.get("user-agent")
        )
    except RefreshError:
        unauthorized = JSONResponse({"detail": "Session expired. Please log in again."}, status_code=401)
        _clear_refresh_cookie(unauthorized)
        return unauthorized

    _set_refresh_cookie(response, new_token, row.expires_at)
    return _token_response(user.id)


# ── POST /auth/logout ──────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(settings.refresh_cookie_name)
    if token:
        await revoke_refresh_token(db, token)
    _clear_refresh_cookie(response)


# ── GET /auth/me ───────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── POST /auth/delete-account ──────────────────────────────────────────────────

@router.post(
    "/delete-account",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"description": "Admins can't delete themselves here"}, 403: {"description": "Wrong password"}},
)
async def delete_account(
    body: DeleteAccount,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes your account and everything of yours: linked LoL accounts, snapshots, analyses and sessions. Asks for the password, with
    an attempt limit, and closes the session. Administrators cannot (they would leave the site with none)."""
    await enforce("delete-account", str(current_user.id), 5, 3600, response)
    if current_user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrators can't delete their own account.")
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong password.")
    await db.delete(current_user)
    await db.commit()
    _clear_refresh_cookie(response)
