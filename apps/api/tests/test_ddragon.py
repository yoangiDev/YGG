"""Endpoints de Data Dragon (consultan la red real de Riot)."""

import re

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestDDragonVersion:
    def test_get_version(self):
        response = client.get("/ddragon/version")
        assert response.status_code == 200
        # La versión real cambia con cada parche; solo comprobamos el formato.
        assert re.fullmatch(r"\d+\.\d+\.\d+", response.json())


class TestDDragonItems:
    def test_get_all_items(self):
        response = client.get("/ddragon/items")
        assert response.status_code == 200
        assert len(response.json()) > 0

    def test_get_item_found(self):
        response = client.get("/ddragon/items/3031")
        assert response.status_code == 200
        assert "name" in response.json()

    def test_get_item_not_found(self):
        assert client.get("/ddragon/items/99999").status_code == 404

    def test_get_item_icon(self):
        response = client.get("/ddragon/items/3031/icon")
        assert response.status_code == 200
        assert response.json()["url"].endswith("/img/item/3031.png")


class TestDDragonSpells:
    def test_get_all_spells(self):
        response = client.get("/ddragon/spells")
        assert response.status_code == 200
        assert len(response.json()) > 0

    def test_get_spell_by_numeric_key(self):
        # Flash tiene la key numérica "4" en DDragon
        response = client.get("/ddragon/spells/4")
        assert response.status_code == 200
        assert response.json()["name"] == "Flash"

    def test_get_spell_not_found(self):
        assert client.get("/ddragon/spells/99999").status_code == 404


class TestDDragonRunes:
    def test_get_all_runes(self):
        response = client.get("/ddragon/runes")
        assert response.status_code == 200
        assert len(response.json()) > 0

    def test_get_rune_by_id_tree(self):
        response = client.get("/ddragon/runes/8100")
        assert response.status_code == 200
        assert response.json()["name"] == "Domination"

    def test_get_rune_by_id_keystone(self):
        response = client.get("/ddragon/runes/8112")
        assert response.status_code == 200
        assert response.json()["key"] == "Electrocute"

    def test_get_rune_not_found(self):
        assert client.get("/ddragon/runes/99999").status_code == 404

    def test_get_rune_icon_keystone(self):
        response = client.get("/ddragon/runes/8112/icon")
        assert response.status_code == 200
        assert "url" in response.json()

    def test_get_rune_icon_tree(self):
        response = client.get("/ddragon/runes/8100/icon")
        assert response.status_code == 200
        assert "url" in response.json()


class TestDDragonMap:
    def test_map_redirects_to_riot_cdn(self):
        # Ya no se guarda en el disco efímero del servidor ni se sirve con StaticFiles.
        response = client.get("/ddragon/map", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"].startswith("https://ddragon.leagueoflegends.com/cdn/")
        assert response.headers["location"].endswith("/img/map/map11.png")

    def test_get_map_url(self):
        response = client.get("/ddragon/map/url")
        assert response.status_code == 200
        assert "map11.png" in response.json()["url"]
