"""Reading LoL replays (.rofl, ROFL2 format from patch 14 onward) without touching the client.

    pip install zstandard
    python research/replays/rofl.py <replay.rofl> [match-v5 timeline.json]

What is read without reverse engineering:

- Metadata: JSON at the end of the file (its length in the last 4 bytes) with the
  duration and the ~300 final stats of each player (statsJson).
- Blocks: each with a 17-byte header (id u32, next u32, type u8,
  decompressed size u32, compressed u32) and a zstd frame. Type 1 = fragment,
  2 = full snapshot (keyframe), 3 = header. Not encrypted at file level.
- Packets: a marker byte and then time, length, type and entity. Marker
  bits: 0x80 relative time (1 byte, ms; otherwise f32 in seconds), 0x10 length
  in 1 byte (otherwise u32), 0x40 same type as the previous (otherwise u16), 0x20 relative
  entity (i8; otherwise u32).

What isn't: the content of each packet is obfuscated with byte-by-byte substitution, one
table per position, and Riot shuffles types and tables on every patch. With the official timeline
of the same match the types are identified (the one that matches each purchase, death
or level-up of the player) and tables can be learned with known data.
In patch 16.18 the 10 champions are consecutive entities, in the order of the
match-v5 participants.

Types and tables belong to the patch, not the match (checked with two matches of
16.18): purchase 0x033a, level-up 0x01a5, ability 0x04c7, death 0x04dc and
ward 0x00db. In the purchase, bytes 8-11 are the price (f32, bytes reversed) and 12-13
the item id; tables learned in one match decrypt 96% of the purchases in
the other that fall on values already seen.
"""

from __future__ import annotations

import bisect
import collections
import json
import struct
import sys
from pathlib import Path
from typing import Any, NamedTuple

import zstandard

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


class Packet(NamedTuple):
    time: float  # match seconds
    kind: int  # type (changes with every patch)
    entity: int  # network id of the entity (champion, turret, minion...) or 0
    payload: bytes  # ofuscado


def read(path: Path) -> tuple[dict[str, Any], list[tuple[int, int, bytes]]]:
    """(metadata with statsJson already parsed, [(id, type, decompressed data)])."""
    raw = path.read_bytes()
    end = len(raw) - 4 - struct.unpack_from("<I", raw, len(raw) - 4)[0]
    meta = json.loads(raw[end : len(raw) - 4])
    meta["statsJson"] = json.loads(meta["statsJson"])
    blocks, i = [], raw.find(ZSTD_MAGIC)
    while i != -1 and i < end:
        block_id, _next, kind, size, compressed = struct.unpack_from("<IIBII", raw, i - 17)
        data = zstandard.ZstdDecompressor().decompress(raw[i : i + compressed], max_output_size=size)
        blocks.append((block_id, kind, data))
        i = raw.find(ZSTD_MAGIC, i + compressed)
    return meta, blocks


def packets(data: bytes) -> list[Packet]:
    out: list[Packet] = []
    pos, time, kind, entity = 0, 0.0, 0, 0
    while pos < len(data):
        marker = data[pos]
        pos += 1
        if marker & 0x80:
            time += data[pos] / 1000
            pos += 1
        else:
            time = struct.unpack_from("<f", data, pos)[0]
            pos += 4
        if marker & 0x10:
            length = data[pos]
            pos += 1
        else:
            length = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        if not marker & 0x40:
            kind = struct.unpack_from("<H", data, pos)[0]
            pos += 2
        if marker & 0x20:
            entity += struct.unpack_from("<b", data, pos)[0]
            pos += 1
        else:
            entity = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        if pos + length > len(data):
            raise ValueError(f"packet cut at byte {pos}")
        out.append(Packet(time, kind, entity, data[pos : pos + length]))
        pos += length
    return out


def game_packets(blocks: list[tuple[int, int, bytes]]) -> list[Packet]:
    """The packets of the fragments (type 1), in order: snapshots repeat state."""
    return [p for _id, kind, data in blocks if kind == 1 for p in packets(data)]


def hero_entities(all_packets: list[Packet]) -> list[int]:
    """The 10 champions: the 10 consecutive entities with the most packets (participants 1-10 in order)."""
    counts = collections.Counter(p.entity for p in all_packets if p.entity)
    start = max(counts, key=lambda e: sum(counts.get(e + k, 0) for k in range(10)))
    return [start + k for k in range(10)]


def identify(all_packets: list[Packet], timeline: dict[str, Any], window: float = 0.35) -> dict[str, list[tuple[float, int]]]:
    """For each timeline event type: (% of events with a player packet within ±window s, type), the best 3."""
    heroes = hero_entities(all_packets)
    times: dict[int, dict[int, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in all_packets:
        times[p.kind][p.entity].append(p.time)
    who = {"ITEM_PURCHASED": "participantId", "LEVEL_UP": "participantId", "SKILL_LEVEL_UP": "participantId",
           "WARD_PLACED": "creatorId", "CHAMPION_KILL": "victimId"}
    events = [e for f in timeline["info"]["frames"] for e in f["events"] if e.get(who.get(e["type"], ""), 0) > 0]
    out: dict[str, list[tuple[float, int]]] = {}
    for name, key in who.items():
        chosen = [e for e in events if e["type"] == name]
        scores = []
        for kind, by_entity in times.items():
            hits = 0
            for e in chosen:
                ts = by_entity.get(heroes[e[key] - 1], [])
                x = e["timestamp"] / 1000
                i = bisect.bisect_left(ts, x - window)
                hits += i < len(ts) and ts[i] <= x + window
            scores.append((hits / len(chosen), kind))
        out[name] = sorted(scores, reverse=True)[:3]
    return out


def main() -> None:
    meta, blocks = read(Path(sys.argv[1]))
    all_packets = game_packets(blocks)
    kinds = collections.Counter(kind for _id, kind, _data in blocks)
    print(f"{meta['gameLength'] / 1000:.0f} s · {len(meta['statsJson'])} players · blocks {dict(kinds)}")
    print(f"{len(all_packets)} packets, {len({p.kind for p in all_packets})} types · champions: "
          f"{[hex(e) for e in hero_entities(all_packets)[:1]]}… in participant order")
    if len(sys.argv) > 2:
        timeline = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        for name, best in identify(all_packets, timeline).items():
            print(f"  {name:<15}", ", ".join(f"0x{kind:04x} {100 * rate:.0f} %" for rate, kind in best))


if __name__ == "__main__":
    main()
