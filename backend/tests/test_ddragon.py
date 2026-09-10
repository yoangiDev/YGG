from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestDDragonVersion:
    def test_get_version(self):
        response = client.get("/ddragon/version")
        assert response.status_code == 200
        assert response.json() == "16.10.1"


class TestDDragonItems:
    def test_get_all_items(self):
        response = client.get("/ddragon/items")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_get_item_found(self):
        response = client.get("/ddragon/items/3031")
        assert response.status_code == 200
        assert "name" in response.json()

    def test_get_item_not_found(self):
        response = client.get("/ddragon/items/99999")
        assert response.status_code == 404

    def test_get_item_icon(self):
        response = client.get("/ddragon/items/3031/icon")
        assert response.status_code == 200
        assert "url" in response.json()


class TestDDragonSpells:
    def test_get_all_spells(self):
        response = client.get("/ddragon/spells")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_get_spell_by_numeric_key(self):
        # Flash tiene la key numérica "4" en DDragon
        response = client.get("/ddragon/spells/4")
        assert response.status_code == 200
        assert response.json()["name"] == "Flash"

    def test_get_spell_not_found(self):
        response = client.get("/ddragon/spells/99999")
        assert response.status_code == 404


class TestDDragonRunes:
    def test_get_all_runes(self):
        response = client.get("/ddragon/runes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_rune_by_id_tree(self):
        response = client.get("/ddragon/runes/8100")
        assert response.status_code == 200
        assert response.json()["name"] == "Domination"

    def test_get_rune_by_id_keystone(self):
        response = client.get("/ddragon/runes/8112")
        assert response.status_code == 200
        assert response.json()["key"] == "Electrocute"

    def test_get_rune_not_found(self):
        response = client.get("/ddragon/runes/99999")
        assert response.status_code == 404

    def test_get_rune_icon_keystone(self):
        response = client.get("/ddragon/runes/8112/icon")
        assert response.status_code == 200
        assert "url" in response.json()

    def test_get_rune_icon_tree(self):
        response = client.get("/ddragon/runes/8100/icon")
        assert response.status_code == 200
        assert "url" in response.json()


class TestDDragonMap:
    def test_get_map_image(self):
        response = client.get("/ddragon/map")
        # El mapa se descarga durante la inicialización de ddragon, por lo que debería retornar 200
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_get_map_url(self):
        response = client.get("/ddragon/map/url")
        assert response.status_code == 200
        assert "url" in response.json()
        assert "map11.png" in response.json()["url"]
