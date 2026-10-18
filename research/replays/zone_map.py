"""Draws the map with the name of each zone (`zones.json`) so they can be changed by eye, and saves what you edit.

    python research/replays/zone_map.py            # and opens http://localhost:8765 (zones) or http://localhost:8765/?mapa=bushes

Each zone is a polygon with a name and, if it belongs to a team, its side; the order of the list is the priority (the first zone that
contains a point is its name). `coach.place` reads that same file, so what you save here is what the analyses say.
The bushes (`bushes.json`) have their own map, without the zones: the decoder's image with the bushes in green, and the user draws them with the same tools.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).parent
FILES, PAGE = {"zones": HERE / "zones.json", "bushes": HERE / "bushes.json"}, HERE / "zone_map.html"
BACKGROUND = HERE / "bush_map.png"  # the bush map's background: the decoder's image with its bushes in green (`bushes_from_wad.py`)


def validate(data: dict, may_be_empty: bool = False) -> list[dict]:
    zones = data["zones"]
    ids = [z["id"] for z in zones]
    assert (zones or may_be_empty) and len(set(ids)) == len(ids), "duplicate or empty ids"
    for z in zones:
        assert z["name"].strip() and z["side"] in (None, "blue", "red"), z
        assert len(z["polygon"]) >= 3 and all(len(p) == 2 for p in z["polygon"]), z["id"]
    return zones


class Server(BaseHTTPRequestHandler):
    def answers(self, body: bytes, kind: str, state: int = 200) -> None:
        self.send_response(state)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file_(self) -> Path:
        return FILES.get(parse_qs(urlparse(self.path).query).get("map", ["zones"])[0], FILES["zones"])

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self.answers(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path == "/background.png":
            self.answers(BACKGROUND.read_bytes(), "image/png")
        elif path == "/data":
            self.answers(self.file_().read_bytes(), "application/json")
        else:
            self.answers(b"", "text/plain", 404)

    def do_POST(self) -> None:  # noqa: N802
        try:
            zones = validate(json.loads(self.rfile.read(int(self.headers["Content-Length"]))), self.file_() != FILES["zones"])
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            return self.answers(f"invalid zones: {error}".encode(), "text/plain", 400)
        self.file_().write_text('{"zones": [\n' + ",\n".join(json.dumps(z, ensure_ascii=False) for z in zones) + "\n]}\n", encoding="utf-8")
        self.answers(b"ok", "text/plain")

    def log_message(self, *_args) -> None:
        pass


if __name__ == "__main__":
    print("zone map at http://localhost:8765  (Ctrl+C to close)")
    ThreadingHTTPServer(("127.0.0.1", 8765), Server).serve_forever()
