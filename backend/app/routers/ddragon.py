from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from typing import Optional

from app.service.ddragon_client import (
    get_ddragon_client,
    DDragonClient
)

router = APIRouter(prefix="/ddragon", tags=["ddragon"])


@router.get("/version")
async def get_version() -> str:
    client = await get_ddragon_client()
    return client.version


@router.get("/items")
async def get_items() -> dict:
    client = await get_ddragon_client()
    return client.items


@router.get("/items/{item_id}")
async def get_item(item_id: str):
    client = await get_ddragon_client()
    item = client.get_item_data(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items/{item_id}/icon")
async def get_item_icon(item_id: int):
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=500, detail="Version not loaded")
    return {"url": DDragonClient.item_icon_url(client.version, item_id)}


@router.get("/spells")
async def get_spells() -> dict:
    client = await get_ddragon_client()
    return client.spells


@router.get("/spells/{key}")
async def get_spell(key: str):
    client = await get_ddragon_client()
    spell = client.get_spell_data_by_key(key)
    if not spell:
        raise HTTPException(status_code=404, detail="Spell not found")
    return spell


@router.get("/runes")
async def get_runes() -> list:
    client = await get_ddragon_client()
    return client.runes


@router.get("/runes/{rune_id}")
async def get_rune(rune_id: int):
    client = await get_ddragon_client()
    rune_id_str = str(rune_id)
    
    for rune in client.runes:
        if str(rune.get("id")) == rune_id_str:
            return rune
        
        for slot in rune.get("slots", []):
            for nested_rune in slot.get("runes", []):
                if str(nested_rune.get("id")) == rune_id_str:
                    return nested_rune
    
    raise HTTPException(status_code=404, detail="Rune not found")


@router.get("/runes/{rune_id}/icon")
async def get_rune_icon(rune_id: int):
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=500, detail="Version not loaded")
    
    rune_id_str = str(rune_id)
    
    for rune in client.runes:
        if str(rune.get("id")) == rune_id_str:
            icon_path = rune.get("icon")
            if not icon_path:
                raise HTTPException(status_code=404, detail="Rune icon not found")
            return {"url": DDragonClient.rune_icon_url(client.version, icon_path)}
        
        for slot in rune.get("slots", []):
            for nested_rune in slot.get("runes", []):
                if str(nested_rune.get("id")) == rune_id_str:
                    icon_path = nested_rune.get("icon")
                    if not icon_path:
                        raise HTTPException(status_code=404, detail="Rune icon not found")
                    return {"url": DDragonClient.rune_icon_url(client.version, icon_path)}
    
    raise HTTPException(status_code=404, detail="Rune not found")


@router.get("/map")
async def get_map():
    """Redirige a la imagen del mapa (map11.png) servida de forma estática."""
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=500, detail="Version not loaded")
    
    path = client.get_map_path()
    if not path:
        raise HTTPException(status_code=404, detail="Map image not found or not cached")
        
    return RedirectResponse(url=f"/static/ddragon/{client.version}_map11.png")


@router.get("/map/static-url")
async def get_map_static_url():
    """Retorna la URL estática local del mapa en nuestro servidor."""
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=500, detail="Version not loaded")
    
    path = client.get_map_path()
    if not path:
        raise HTTPException(status_code=404, detail="Map image not found or not cached")
        
    return {"url": f"/static/ddragon/{client.version}_map11.png"}


@router.get("/map/url")
async def get_map_url():
    """Retorna la URL externa de la imagen del mapa en Data Dragon."""
    client = await get_ddragon_client()
    if not client.version:
        raise HTTPException(status_code=500, detail="Version not loaded")
    return {"url": DDragonClient.map_image_url(client.version)}