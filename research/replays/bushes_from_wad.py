"""Extracts the Rift map from the game's navigation grid: `bush_map.png` (floor, walls, river, bases and bushes in green, the background of the
bush editor) and `bushes_auto.json` (each bush's outline, only as a reference: the real ones, with their names, are drawn by the user
in `bushes.json` over the image).

    python research/replays/bushes_from_wad.py [Map11.wad.client] [--output bushes_auto.json]

`zstandard` is needed (it is in the decoder's environment). The grid is `AIPath_SRX_3.aimesh_ngrid` from Map11.wad.client (version 7, 50-unit
cell, 295x296 cells). It is not the decoder's `mapa.html` one (`AIPath_SRX`, an earlier layout): with champion positions from 8 matches of 16.20,
SRX leaves 4.7% inside walls and SRX_3 0.43% (the other named variants, between 4.4% and 4.9%; `AIPath_SRX_2` is the same as SRX).
Each cell carries its height (f32, 48 bytes from the next) and, after all the cells, a u16 of vision flags: bit 0 is the bush and bit 1 the wall.
Contiguous bushes are grouped and each one's outline is drawn, simplified.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import zlib
from pathlib import Path

import zstandard

WAD = Path("C:/Riot Games/League of Legends/Game/DATA/FINAL/Maps/Shipping/Map11.wad.client")
CELL = 50.0
NAVGRID_PATH = "assets/maps/navgrid/map11/aipath_srx_3.aimesh_ngrid"  # the .wad stores each file by the xxh64 of its lowercase path
MIN_CELLS = 3  # a bush of fewer cells is grid noise
TOLERANCE = 45.0  # map units the simplified outline may stray from the real one


def xxh64(data: bytes) -> int:
    """xxHash64 with seed 0 (the hash by which the .wad names its files)."""
    M, P1, P2, P3, P4, P5 = (1 << 64) - 1, 11400714785074694791, 14029467366897019727, 1609587929392839161, 9650029242287828579, 2870177450012600261

    def role(x: int, r: int) -> int:
        return ((x << r) | (x >> (64 - r))) & M

    def xxh_round(acc: int, v: int) -> int:
        return role((acc + v * P2) & M, 31) * P1 & M

    n, i = len(data), 0
    if n >= 32:
        v = [(P1 + P2) & M, P2, 0, (-P1) & M]
        while i <= n - 32:
            v = [xxh_round(v[k], struct.unpack_from("<Q", data, i + 8 * k)[0]) for k in range(4)]
            i += 32
        h = (role(v[0], 1) + role(v[1], 7) + role(v[2], 12) + role(v[3], 18)) & M
        for x in v:
            h = ((h ^ xxh_round(0, x)) * P1 + P4) & M
    else:
        h = P5
    h = (h + n) & M
    while i <= n - 8:
        h = role(h ^ xxh_round(0, struct.unpack_from("<Q", data, i)[0]), 27) * P1 + P4 & M
        i += 8
    if i <= n - 4:
        h = role(h ^ (struct.unpack_from("<I", data, i)[0] * P1 & M), 23) * P2 + P3 & M
        i += 4
    for b in data[i:]:
        h = role(h ^ (b * P5 & M), 11) * P1 & M
    h ^= h >> 33
    h = h * P2 & M
    h ^= h >> 29
    h = h * P3 & M
    return h ^ (h >> 32)


def read_grid(wad: Path) -> tuple[list[int], list[float], tuple[float, float], int, int]:
    """(flags and heights per cell in order x + z·nx, minimum corner (x, z), nx, nz) of the .wad's navigation grid."""
    with wad.open("rb") as fh:
        n = struct.unpack_from("<I", fh.read(272), 268)[0]
        table = fh.read(32 * n)
        wanted = xxh64(NAVGRID_PATH.encode())
        for i in range(n):
            hash_, off, csize, size, kind = struct.unpack_from("<QIIIB", table, 32 * i)
            if hash_ != wanted:
                continue
            fh.seek(off)
            raw = zstandard.ZstdDecompressor().decompress(fh.read(csize), max_output_size=size)
            assert raw[0] == 7, "the grid is no longer version 7: the format needs reviewing"
            min_x, _y, min_z = struct.unpack_from("<3f", raw, 3)
            cell, nx, nz = struct.unpack_from("<fII", raw, 27)
            assert cell == CELL, cell
            since = 39 + nx * nz * 48  # after the 48-byte cells come the vision flags, one u16 per cell
            flags = list(struct.unpack_from(f"<{nx * nz}H", raw, since))
            heights = struct.unpack_from(f"<{nx * nz * 12}f", raw, 39)[::12]  # the height opens each 48-byte cell
            return flags, list(heights), (min_x, min_z), nx, nz
    raise SystemExit(f"cannot find {NAVGRID_PATH} in the .wad")


def groups(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    """Components of contiguous cells (8 neighbours)."""
    seen_, output = set(), []
    for c in sorted(cells):
        if c in seen_:
            continue
        stack, g = [c], set()
        while stack:
            x, z = stack.pop()
            if (x, z) in seen_:
                continue
            seen_.add((x, z))
            g.add((x, z))
            stack += [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in cells]
        output.append(g)
    return output


def outline(g: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """The group's outer edge, in grid vertices and counter-clockwise."""
    leave: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for x, z in g:
        for a, b, neighbour in (((x, z), (x + 1, z), (x, z - 1)), ((x + 1, z), (x + 1, z + 1), (x + 1, z)),
                             ((x + 1, z + 1), (x, z + 1), (x, z + 1)), ((x, z + 1), (x, z), (x - 1, z))):
            if neighbour not in g:
                leave.setdefault(a, []).append(b)
    loops = []
    while leave:
        start = next(iter(leave))
        loop, current = [start], start
        while True:
            next_ = leave[current].pop()
            if not leave[current]:
                del leave[current]
            if next_ == start:
                break
            loop.append(next_)
            current = next_
        loops.append(loop)
    return max(loops, key=lambda p: abs(_area(p)))


def _area(p: list[tuple[float, float]]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1])) / 2


def _rdp(p: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker over an open line."""
    if len(p) < 3:
        return p
    (x1, z1), (x2, z2) = p[0], p[-1]
    length = math.hypot(x2 - x1, z2 - z1) or 1.0
    far = max(range(1, len(p) - 1), key=lambda i: abs((x2 - x1) * (z1 - p[i][1]) - (x1 - p[i][0]) * (z2 - z1)) / length)
    if abs((x2 - x1) * (z1 - p[far][1]) - (x1 - p[far][0]) * (z2 - z1)) / length <= tol:
        return [p[0], p[-1]]
    return _rdp(p[:far + 1], tol)[:-1] + _rdp(p[far:], tol)


def simplify(p: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker over a closed outline: it is split at the vertex farthest from the first."""
    k = max(range(len(p)), key=lambda i: math.dist(p[0], p[i]))
    return _rdp(p[:k + 1], tol)[:-1] + _rdp(p[k:] + [p[0]], tol)[:-1]


PX = 8  # pixels per image cell
COLORS = {"out": (0, 0, 0), "wall": (16, 24, 16), "floor": (145, 152, 112), "river": (18, 156, 197), "base": (101, 136, 142), "bush": (34, 224, 107)}
RIVER_MAX, RIVER_MIN_CELLS, BASE_MIN = 15.0, 1000, 75.0  # river: low zones of more than 1000 cells; bases: above a height of 75


def image(flags: list[int], heights: list[float], nx: int, nz: int) -> bytes:
    """The cells as RGB pixels (the bottom row, z = 0, last): floor, walls (those joined to the grid edge are the outside, in black),
    river, bases and bushes in strong green."""
    wall = [b & 2 != 0 for b in flags]
    outside, stack = set(), [c for c in range(nx * nz) if wall[c] and (c % nx in (0, nx - 1) or c // nx in (0, nz - 1))]
    while stack:
        c = stack.pop()
        if c in outside:
            continue
        outside.add(c)
        x, z = c % nx, c // nx
        stack += [v for v, ok in ((c - 1, x > 0), (c + 1, x < nx - 1), (c - nx, z > 0), (c + nx, z < nz - 1)) if ok and wall[v] and v not in outside]
    kills, river = {c for c in range(nx * nz) if not wall[c] and heights[c] < RIVER_MAX}, set()
    while kills:  # components of low cells: the river is those of more than RIVER_MIN_CELLS
        c = kills.pop()
        group, stack = {c}, [c]
        while stack:
            c = stack.pop()
            x = c % nx
            for v, ok in ((c - 1, x > 0), (c + 1, x < nx - 1), (c - nx, c >= nx), (c + nx, c < nx * (nz - 1))):
                if ok and v in kills:
                    kills.discard(v)
                    group.add(v)
                    stack.append(v)
        if len(group) > RIVER_MIN_CELLS:
            river |= group
    def kind(c: int) -> str:
        if c in outside:
            return "out"
        if wall[c]:
            return "wall"
        if flags[c] & 1:
            return "bush"
        return "base" if heights[c] > BASE_MIN else "river" if c in river else "floor"
    rows = []
    for z in range(nz - 1, -1, -1):
        row = b"".join(bytes(COLORS[kind(z * nx + x)]) * PX for x in range(nx))
        rows += [row] * PX
    return b"".join(rows)


def write_png(path: Path, rgb: bytes, width: int, height: int) -> None:
    """An RGB PNG with no dependencies beyond zlib."""
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
    raw = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    signature = b"\x89PNG\r\n\x1a\n"
    path.write_bytes(signature + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    print(f"{width}x{height} → {path}")


def main() -> None:
    wad = Path(next((a for a in sys.argv[1:] if a.endswith(".client")), WAD))
    output = Path(sys.argv[sys.argv.index("--output") + 1]) if "--output" in sys.argv else Path(__file__).with_name("bushes_auto.json")
    flags, heights, (min_x, min_z), nx, nz = read_grid(wad)
    write_png(Path(__file__).with_name("bush_map.png"), image(flags, heights, nx, nz), nx * PX, nz * PX)
    bush = {(i % nx, i // nx) for i, b in enumerate(flags) if b & 1}
    bushes = [g for g in groups(bush) if len(g) >= MIN_CELLS]
    previous_ones = {z["id"]: z for z in json.loads(output.read_text(encoding="utf-8"))["zones"]} if output.exists() else {}
    zones = []
    for g in bushes:
        polygon = simplify([(min_x + x * CELL, min_z + z * CELL) for x, z in outline(g)], TOLERANCE)
        polygon = [[round(x / 10) * 10, round(z / 10) * 10] for x, z in polygon]
        cx, cz = (sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon))
        zones.append((cx + cz, cx, cz, polygon))
    zones.sort()
    items = []
    for n, (_k, cx, cz, polygon) in enumerate(zones, 1):
        id_ = f"bush-{round(cx)}-{round(cz)}"  # the id comes from where it is, to keep the name if it is redone
        items.append({"id": id_, "name": previous_ones.get(id_, {}).get("name", f"bush {n}"), "side": None, "polygon": polygon})
    output.write_text('{"zones": [\n' + ",\n".join(json.dumps(z, ensure_ascii=False) for z in items) + "\n]}\n", encoding="utf-8")
    print(f"{len(bush)} bush cells in {len(items)} bushes → {output}")


if __name__ == "__main__":
    main()
