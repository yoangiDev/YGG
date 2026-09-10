from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.league import RankCutoffsResponse
from app.service.league_service import get_rank_cutoffs, platform_from_region

router = APIRouter(prefix="/league", tags=["league"])


@router.get(
    "/cutoffs",
    response_model=RankCutoffsResponse,
    responses={503: {"description": "Riot API unavailable"}},
)
async def read_rank_cutoffs(
    region: str = Query(..., description="Player region, e.g. EUW, NA, KR"),
    refresh: bool = Query(False, description="Force refresh from Riot API"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Grandmaster and Challenger LP cutoffs for a platform (cached for 4 hours).

    - Grandmaster cutoff: LP of the player at overall rank 1000 (last GM slot).
    - Challenger cutoff: LP of the player at overall rank 300 (last Challenger slot).
    """
    try:
        record = await get_rank_cutoffs(db, region, refresh=refresh)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RankCutoffsResponse(
        region=region.upper(),
        platform=platform_from_region(region),
        grandmaster_cutoff_lp=record.grandmaster_cutoff_lp,
        challenger_cutoff_lp=record.challenger_cutoff_lp,
        fetched_at=record.fetched_at,
    )
