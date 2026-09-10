from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.passwords import NewPassword, hash_password
from app.db.models.player import Player
from app.db.models.user import User
from app.db.session import get_db
from app.queries import load
from app.schemas.common import Page, PageParams

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: str


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: NewPassword
    role: str = "user"


class TierCount(BaseModel):
    tier: str
    count: int


class RegionCount(BaseModel):
    region: str
    count: int


class TopUser(BaseModel):
    username: str
    player_count: int


class AdminPlayerOut(BaseModel):
    id: int
    game_name: str
    tag_line: str
    region: str
    nickname: str
    role: str
    tier: str
    rank: str
    lp: int
    wins: int
    losses: int
    owner_username: str


class GlobalStats(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    total_players: int
    total_snapshots: int
    total_matches: int
    tier_distribution: list[TierCount]
    region_distribution: list[RegionCount]
    top_users: list[TopUser]


class DeleteInactiveResult(BaseModel):
    deleted: int


async def _get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def _validate_role(role: str) -> None:
    if role not in ("user", "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role. Use 'user' or 'admin'.")


# ── Jugadores ──────────────────────────────────────────────────────────────────

@router.get("/players/", response_model=Page[AdminPlayerOut])
async def list_all_players(
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    total = await db.scalar(select(func.count(Player.id))) or 0
    rows = await db.execute(
        select(Player, User.username)
        .join(User, User.id == Player.user_id)
        .order_by(User.username, Player.game_name, Player.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    items = [
        AdminPlayerOut(
            id=player.id,
            game_name=player.game_name,
            tag_line=player.tag_line,
            region=player.region,
            nickname=player.nickname or "",
            role=player.role.value if player.role else "",
            tier=player.tier or "",
            rank=player.rank or "",
            lp=player.lp or 0,
            wins=player.wins or 0,
            losses=player.losses or 0,
            owner_username=username,
        )
        for player, username in rows
    ]
    return Page[AdminPlayerOut](items=items, total=total, limit=page.limit, offset=page.offset)


@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_player(player_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    player = await db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    await db.delete(player)
    await db.commit()


# ── Estadísticas ───────────────────────────────────────────────────────────────

@router.get("/stats/", response_model=GlobalStats)
async def get_global_stats(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    counts = (await db.execute(load("global_counts"))).mappings().one()
    player_count = func.count(Player.id)

    tier_rows = await db.execute(select(Player.tier, player_count).where(Player.tier != "").group_by(Player.tier))
    region_rows = await db.execute(
        select(Player.region, player_count).group_by(Player.region).order_by(player_count.desc())
    )
    top_rows = await db.execute(
        select(User.username, player_count)
        .outerjoin(Player, Player.user_id == User.id)
        .group_by(User.id, User.username)
        .order_by(player_count.desc())
        .limit(5)
    )

    return GlobalStats(
        total_users=counts["total_users"],
        active_users=counts["active_users"],
        inactive_users=counts["total_users"] - counts["active_users"],
        total_players=counts["total_players"],
        total_snapshots=counts["total_snapshots"],
        total_matches=counts["total_matches"],
        tier_distribution=[TierCount(tier=tier, count=count) for tier, count in tier_rows],
        region_distribution=[RegionCount(region=region, count=count) for region, count in region_rows],
        top_users=[TopUser(username=name, player_count=count) for name, count in top_rows],
    )


# ── Usuarios ───────────────────────────────────────────────────────────────────

@router.get("/users/", response_model=Page[UserOut])
async def list_users(page: PageParams = Depends(), db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    total = await db.scalar(select(func.count(User.id))) or 0
    users = await db.scalars(select(User).order_by(User.id).limit(page.limit).offset(page.offset))
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users], total=total, limit=page.limit, offset=page.offset
    )


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: int,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot change your own role.")
    _validate_role(body.role)
    user = await _get_user(db, user_id)
    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/active", response_model=UserOut)
async def toggle_user_active(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")
    user = await _get_user(db, user_id)
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/inactive", response_model=DeleteInactiveResult)
async def delete_inactive_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    inactive = list(await db.scalars(select(User).where(User.is_active.is_(False), User.id != current_user.id)))
    for user in inactive:
        await db.delete(user)
    await db.commit()
    return DeleteInactiveResult(deleted=len(inactive))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")
    await db.delete(await _get_user(db, user_id))
    await db.commit()


@router.post("/users/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    _validate_role(body.role)
    if await db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already registered.")
    if await db.scalar(select(User.id).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This username is already taken.")
    user = User(email=body.email, username=body.username, hashed_password=hash_password(body.password), role=body.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
