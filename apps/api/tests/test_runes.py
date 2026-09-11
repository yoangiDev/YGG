import pytest
from app.service.ddragon_client import get_ddragon_client


class TestDDragonClientRunes:
    """Tests del servicio DDragonClient a nivel de capa de servicio (sin HTTP)."""

    async def test_runes_loaded(self):
        client = await get_ddragon_client()
        assert len(client.runes) > 0, "El cliente DDragon debe cargar al menos un árbol de runas"

    async def test_rune_tree_has_expected_fields(self):
        client = await get_ddragon_client()
        tree = client.runes[0]
        assert "id"    in tree
        assert "name"  in tree
        assert "slots" in tree
        assert isinstance(tree["slots"], list)

    async def test_domination_tree_exists(self):
        client = await get_ddragon_client()
        names = [r["name"] for r in client.runes]
        assert "Domination" in names

    async def test_electrocute_keystone_exists(self):
        client = await get_ddragon_client()
        for tree in client.runes:
            for slot in tree.get("slots", []):
                for rune in slot.get("runes", []):
                    if rune.get("key") == "Electrocute":
                        return
        pytest.fail("Electrocute keystone no encontrado en los datos de runas")
