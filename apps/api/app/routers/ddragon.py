"""Datos estáticos de Data Dragon. Las imágenes se sirven directamente desde el CDN de Riot."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app.schemas.system import UrlResponse
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


@router.get("/items/{item_id}", response_model=dict[str, Any])
async def get_item(item_id: str):
    item = (await _loaded_client()).get_item(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.get("/items/{item_id}/icon", response_model=UrlResponse)
async def get_item_icon(item_id: int):
    client = await _loaded_client()
    return UrlResponse(url=client.item_icon_url(client.version, item_id))


@router.get("/spells", response_model=dict[str, Any])
async def get_spells():
    return (await _loaded_client()).spells


@router.get("/spells/{key}", response_model=dict[str, Any])
async def get_spell(key: str):
    spell = (await _loaded_client()).get_spell_by_key(key)
    if not spell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spell not found")
    return spell


@router.get("/runes", response_model=list[dict[str, Any]])
async def get_runes():
    return (await _loaded_client()).runes


@router.get("/runes/{rune_id}", response_model=dict[str, Any])
async def get_rune(rune_id: int):
    rune = (await _loaded_client()).find_rune(rune_id)
    if not rune:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rune not found")
    return rune


@router.get("/runes/{rune_id}/icon", response_model=UrlResponse)
async def get_rune_icon(rune_id: int):
    client = await _loaded_client()
    rune = client.find_rune(rune_id)
    if not rune or not rune.get("icon"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rune not found")
    return UrlResponse(url=client.rune_icon_url(client.version, rune["icon"]))


@router.get("/map", status_code=status.HTTP_307_TEMPORARY_REDIRECT, response_class=RedirectResponse)
async def get_map():
    """Redirige a la imagen del minimapa (map11.png) en el CDN de Riot."""
    client = await _loaded_client()
    return RedirectResponse(client.map_image_url(client.version), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/map/url", response_model=UrlResponse)
async def get_map_url():
    client = await _loaded_client()
    return UrlResponse(url=client.map_image_url(client.version))
