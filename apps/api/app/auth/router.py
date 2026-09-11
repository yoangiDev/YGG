from datetime import datetime

import aiohttp
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password, verify_password_or_dummy
from app.auth.refresh import (
    RefreshError,
    issue_refresh_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.core.config import settings
from app.core.rate_limit import client_ip, enforce, rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import ChangePasswordRequest, TokenResponse, UserLogin, UserRegister, UserResponse

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
        httponly=True,  # inaccesible desde JavaScript: un XSS no puede robarlo
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
    """Canjea la cookie de refresh por un access token nuevo y rota la cookie."""
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


# ── PATCH /auth/me/password ────────────────────────────────────────────────────

@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    data: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current one.",
        )
    current_user.hashed_password = hash_password(data.new_password)
    # Cambiar la contraseña cierra las demás sesiones; esta sigue con un refresh token nuevo.
    await revoke_all_refresh_tokens(db, current_user.id)
    await _start_session(db, current_user, request, response)


# ── PATCH /auth/me/avatar ──────────────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


@router.patch("/me/avatar", response_model=UserResponse)
async def update_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage not configured.")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5 MB.")

    ext = (file.filename or "avatar.jpg").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Use jpg, png or webp.")

    path = f"user_{current_user.id}.{ext}"
    upload_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/avatars/{path}"

    async with aiohttp.ClientSession() as session, session.post(
        upload_url,
        data=content,
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "Content-Type": file.content_type or f"image/{ext}",
            "x-upsert": "true",
        },
    ) as resp:
        if resp.status not in (200, 201):
            raise HTTPException(status_code=502, detail="Storage upload failed.")

    current_user.avatar_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/avatars/{path}"
    await db.commit()
    await db.refresh(current_user)
    return current_user
