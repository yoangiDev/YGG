import bcrypt
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db.models.user import User
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.match import Match
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


# ── GET /admin/players/ ───────────────────────────────────────────────────────

@router.get("/players/", response_model=List[AdminPlayerOut])
def list_all_players(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = (
        db.query(Player, User.username)
        .join(User, User.id == Player.user_id)
        .order_by(User.username, Player.game_name)
        .all()
    )
    result = []
    for player, username in rows:
        result.append(AdminPlayerOut(
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
        ))
    return result


# ── DELETE /admin/players/{id} ────────────────────────────────────────────────

@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    player = db.query(Player).filter(Player.id == player_id).first()
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
    total_users    = db.query(func.count(User.id)).scalar() or 0
    active_users   = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    inactive_users = total_users - active_users
    total_players  = db.query(func.count(Player.id)).scalar() or 0
    total_snapshots= db.query(func.count(Snapshot.id)).scalar() or 0
    total_matches  = db.query(func.count(Match.id)).scalar() or 0

    tier_rows = (
        db.query(Player.tier, func.count(Player.id))
        .filter(Player.tier != "")
        .group_by(Player.tier)
        .all()
    )
    tier_distribution = [TierCount(tier=r[0], count=r[1]) for r in tier_rows]

    region_rows = (
        db.query(Player.region, func.count(Player.id))
        .group_by(Player.region)
        .order_by(func.count(Player.id).desc())
        .all()
    )
    region_distribution = [RegionCount(region=r[0], count=r[1]) for r in region_rows]

    top_rows = (
        db.query(User.username, func.count(Player.id).label("player_count"))
        .join(Player, Player.user_id == User.id, isouter=True)
        .group_by(User.id, User.username)
        .order_by(func.count(Player.id).desc())
        .limit(5)
        .all()
    )
    top_users = [TopUser(username=r[0], player_count=r[1]) for r in top_rows]

    return GlobalStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_players=total_players,
        total_snapshots=total_snapshots,
        total_matches=total_matches,
        tier_distribution=tier_distribution,
        region_distribution=region_distribution,
        top_users=top_users,
    )


# ── GET /admin/users/ ──────────────────────────────────────────────────────────

@router.get("/users/", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.query(User).order_by(User.id).all()


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
    user = db.query(User).filter(User.id == user_id).first()
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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


# ── DELETE /admin/users/inactive ─────────────────────────────────────────────

class DeleteInactiveResult(BaseModel):
    deleted: int

@router.delete("/users/inactive", response_model=DeleteInactiveResult)
def delete_inactive_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    inactive = (
        db.query(User)
        .filter(User.is_active == False, User.id != current_user.id)
        .all()
    )
    count = len(inactive)
    for user in inactive:
        db.delete(user)
    db.commit()
    return DeleteInactiveResult(deleted=count)


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
    user = db.query(User).filter(User.id == user_id).first()
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
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already registered.",
        )
    if db.query(User).filter(User.username == body.username).first():
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
