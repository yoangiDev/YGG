import bcrypt

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db.models.match import Match
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.user import User
from app.db.session import get_db

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
    password: str
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

    model_config = {"from_attributes": True}

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


# ── GET /admin/players/ ───────────────────────────────────────────────────────

@router.get("/players/", response_model=list[AdminPlayerOut])
def list_all_players(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = db.execute(
        select(Player, User.username)
        .join(User, User.id == Player.user_id)
        .order_by(User.username, Player.game_name)
    ).all()
    return [
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


# ── DELETE /admin/players/{id} ────────────────────────────────────────────────

@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    db.delete(player)
    db.commit()


# ── GET /admin/stats/ ─────────────────────────────────────────────────────────

@router.get("/stats/", response_model=GlobalStats)
def get_global_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    player_count = func.count(Player.id)

    tier_rows = db.execute(
        select(Player.tier, player_count).where(Player.tier != "").group_by(Player.tier)
    ).all()
    region_rows = db.execute(
        select(Player.region, player_count).group_by(Player.region).order_by(player_count.desc())
    ).all()
    top_rows = db.execute(
        select(User.username, player_count)
        .outerjoin(Player, Player.user_id == User.id)
        .group_by(User.id, User.username)
        .order_by(player_count.desc())
        .limit(5)
    ).all()

    return GlobalStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=total_users - active_users,
        total_players=db.scalar(select(func.count(Player.id))) or 0,
        total_snapshots=db.scalar(select(func.count(Snapshot.id))) or 0,
        total_matches=db.scalar(select(func.count(Match.match_id))) or 0,
        tier_distribution=[TierCount(tier=tier, count=count) for tier, count in tier_rows],
        region_distribution=[RegionCount(region=region, count=count) for region, count in region_rows],
        top_users=[TopUser(username=name, player_count=count) for name, count in top_rows],
    )


# ── GET /admin/users/ ──────────────────────────────────────────────────────────

@router.get("/users/", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return list(db.scalars(select(User).order_by(User.id)))


# ── PATCH /admin/users/{id}/role ───────────────────────────────────────────────

@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role.",
        )
    if body.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Use 'user' or 'admin'.",
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.role = body.role
    db.commit()
    db.refresh(user)
    return user


# ── PATCH /admin/users/{id}/active ────────────────────────────────────────────

@router.patch("/users/{user_id}/active", response_model=UserOut)
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


# ── DELETE /admin/users/inactive ─────────────────────────────────────────────

@router.delete("/users/inactive", response_model=DeleteInactiveResult)
def delete_inactive_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    inactive = list(
        db.scalars(select(User).where(User.is_active.is_(False), User.id != current_user.id))
    )
    for user in inactive:
        db.delete(user)
    db.commit()
    return DeleteInactiveResult(deleted=len(inactive))


# ── DELETE /admin/users/{id} ──────────────────────────────────────────────────

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    db.delete(user)
    db.commit()


# ── POST /admin/users/ ─────────────────────────────────────────────────────────

@router.post("/users/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if body.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Use 'user' or 'admin'.",
        )
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already registered.",
        )
    if db.scalar(select(User.id).where(User.username == body.username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This username is already taken.",
        )
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hashed,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
