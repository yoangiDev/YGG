from unittest.mock import AsyncMock, patch

from ygg_core.ddragon.client import DDragonClient, FileDDragonStore, MemoryDDragonStore

VERSION = "16.10.1"
RUNES = [
    {
        "id": 8100,
        "key": "Domination",
        "name": "Domination",
        "icon": "perk-images/Styles/7200_Domination.png",
        "slots": [{"runes": [{"id": 8112, "key": "Electrocute", "icon": "perk-images/Styles/Domination/Electrocute/Electrocute.png"}]}],
    }
]


def _no_network():
    raise AssertionError("no debería descargar nada")


async def _filled(store):
    await store.save(VERSION, "item.json", {"data": {"3031": {"name": "Infinity Edge"}}})
    await store.save(VERSION, "runesReforged.json", RUNES)
    await store.save(VERSION, "summoner.json", {"data": {"SummonerFlash": {"key": "4", "name": "Flash"}}})
    return store


async def _initialized(store) -> DDragonClient:
    client = DDragonClient(store, session_factory=_no_network)
    with patch.object(client, "fetch_latest_version", AsyncMock(return_value=VERSION)):
        await client.initialize()
    return client


async def test_loads_from_store_without_downloading():
    client = await _initialized(await _filled(MemoryDDragonStore()))
    assert client.version == VERSION
    assert client.get_item(3031) == {"name": "Infinity Edge"}
    assert client.get_item("99999") is None
    assert client.get_spell_by_key(4)["name"] == "Flash"
    assert client.get_spell_by_key("99999") is None


async def test_file_store_roundtrip(tmp_path):
    client = await _initialized(await _filled(FileDDragonStore(tmp_path)))
    assert client.find_rune(8100)["name"] == "Domination"
    assert (tmp_path / f"{VERSION}_item.json").exists()


async def test_incomplete_store_is_not_used():
    store = MemoryDDragonStore()
    await store.save(VERSION, "item.json", {"data": {}})
    client = DDragonClient(store, session_factory=_no_network)
    assert await client._load_all(VERSION) is False


async def test_find_rune_tree_and_keystone():
    client = await _initialized(await _filled(MemoryDDragonStore()))
    assert client.find_rune(8100)["key"] == "Domination"
    assert client.find_rune(8112)["key"] == "Electrocute"
    assert client.find_rune(1) is None


def test_cdn_urls():
    assert DDragonClient.champion_icon_url(VERSION, "Ahri").endswith(f"/cdn/{VERSION}/img/champion/Ahri.png")
    assert DDragonClient.rune_icon_url(VERSION, "perk-images/x.png") == "https://ddragon.leagueoflegends.com/cdn/img/perk-images/x.png"
    assert DDragonClient.map_image_url(VERSION).endswith("/img/map/map11.png")
