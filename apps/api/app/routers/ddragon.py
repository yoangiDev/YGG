"""Static Data Dragon data. Images are served directly from Riot's CDN."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.service.ddragon_client import DDragonClient, get_ddragon_client

router = APIRouter(prefix="/ddragon", tags=["ddragon"])


async def _loaded_client() -> DDragonClient:
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Data Dragon not loaded.")
    return client


@router.get("/version", response_model=str)
async def get_version():
    return (await _loaded_client()).version


@router.get("/items", response_model=dict[str, Any])
async def get_items():
    return (await _loaded_client()).items


@router.get("/spells", response_model=dict[str, Any])
async def get_spells():
    return (await _loaded_client()).spells


@router.get("/runes", response_model=list[dict[str, Any]])
async def get_runes():
    return (await _loaded_client()).runes
