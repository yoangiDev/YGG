"""What happens with each replay you upload on the web: check that it is the match you say, decode it, extract the
player's concepts and compare them with those of their league and role.

Decoding runs in separate processes with the decoder's Python (`decoder_dir/.venv`): it uses unicorn and the game's
exes, which aren't in the API's environment, and its modules would clash with those of `research/replays` (both
have a `rofl.py`). The concepts (`research/replays/features.py`) and the WP curve (`value.py`) run here, with
the same thing that produced the table of 5,144 matches they are compared against (`premium_reference.json`, from
`research/replays/premium_references.py`).

Everything is synchronous, blocking functions: the API calls them with `asyncio.to_thread`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from ygg_core.riot.http import create_secure_session

from app.core.config import settings
from app.service.riot import riot_client

if TYPE_CHECKING:
    from app.db.models.player import Player

logger = structlog.get_logger(__name__)

REFERENCE = Path(__file__).with_name("premium_reference.json")
# what Challengers and Grandmasters choose on leaving base (research/replays/openings.py model)
OPENINGS = Path(__file__).with_name("opening_model.json")
# ponytail: the harvest goes from Gold to Challenger; below that Gold is used for comparison until there is a harvest of those leagues
# (then it is enough to regenerate premium_reference.json)
FALLBACK_TIER = "GOLD"
WP_STEP = 10  # seconds between points of the WP curve that is stored for the chart


def replay_name(match_id: str) -> str:
    """EUW1_123 (Riot) → EUW1-123 (the name of the replay and of what is decoded)."""
    return match_id.replace("_", "-")


def _uploads() -> Path:
    """Where uploaded replays land while they are decoded: its folder, which is emptied at startup."""
    return settings.premium_dir / "uploads"


def _decoded() -> Path:
    return settings.premium_dir / "cosecha"


def new_upload(match_id: str) -> Path:
    """Where to store an uploaded replay: a folder of its own, with a random name, and inside it the name the decoder expects.
    Two users uploading the same match don't overwrite each other's file, and what one uploads never reaches the other's analysis."""
    folder = _uploads() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    return folder / f"{replay_name(match_id)}.rofl"


def stored(match_id: str) -> bool:
    """Whether there are already stored events for that match: the first copy (checked with Riot) is the good one and isn't overwritten."""
    base = _decoded() / replay_name(match_id)
    return all(Path(f"{base}.{ext}").exists() for ext in ("state.csv.gz", "events.json.gz"))


def forget_decoded(match_id: str) -> None:
    """Deletes what was half decoded of that match: `cosecha.py` skips what is already there, and what is left from a
    broken attempt can't sneak into the next one."""
    for old in _decoded().glob(f"{replay_name(match_id)}.*"):
        old.unlink(missing_ok=True)


def matches_riot(match_id: str, record: dict[str, Any]) -> bool:
    """Whether what was decoded is the match Riot says: each player's deaths (from fewest to most, without looking at names)
    have to add up. Without this, whoever uploaded a made-up replay with the id of a match of theirs would fill with false
    events what is later used for statistics and training. A difference of 2 deaths in total is allowed in case the
    decoder misses some; in 2 matches of 16.20 it matched 100%."""
    _research()  # puts research/replays on the path
    import moments  # type: ignore[import-not-found]

    with moments.open_file(_decoded() / f"{replay_name(match_id)}.events.json.gz") as fh:
        events = moments.drop_revived(json.load(fh))
    players = {p["net_id"] for p in events["players"]}
    deaths = Counter(e["net_id"] for e in events["events"] if e["type"] == "Death" and e["net_id"] in players)
    own_rows = sorted(deaths.get(net, 0) for net in players)
    current = sorted(int(p.get("deaths", 0)) for p in record["participants"])
    return len(own_rows) == len(current) and sum(abs(a - b) for a, b in zip(own_rows, current, strict=True)) <= 2


def riot_id(game_name: str, tag_line: str) -> str:
    """Name#TAG for comparing: Riot IDs are case- and whitespace-insensitive."""
    return f"{game_name}#{tag_line}".replace(" ", "").casefold()


# The limits of a .rofl, with slack over what was measured in real matches (80-120 blocks, the largest 1 MB, 30-50 MB
# in total): anything above this isn't a match, and the decoder would decompress it whole in memory.
ROFL_BUILD = re.compile(r"\d{1,3}(?:\.\d{1,5}){3}")  # 16.19.823.0722
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
MAX_META = 1024 * 1024
MAX_BLOCKS = 2000
MAX_BLOCK = 16 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
MAX_NAME = 64


def _zstd_declared_size(data: bytes, start: int) -> int | None:
    """The size declared by the header of a zstd frame (None if it doesn't say). With it, the decompressor reserves that
    memory regardless of the limit you give it: a small frame that declares gigabytes is a bomb."""
    descriptor = data[start + 4]
    single, content_flag, dict_size = descriptor >> 5 & 1, descriptor >> 6, (0, 1, 2, 4)[descriptor & 3]
    width = (1 if single else 0, 2, 4, 8)[content_flag]
    if not width:
        return None
    at = start + 5 + (0 if single else 1) + dict_size  # after the descriptor, the window (if it isn't single-segment) and the dictionary
    size = int.from_bytes(data[at:at + width], "little")
    return size + 256 if content_flag == 1 else size


def _check_blocks(data: bytes, end: int) -> None:
    """Walks the zstd blocks as the decoder does and rejects what doesn't add up or would declare more memory than
    any match uses. It decompresses nothing."""
    at, count, total = data.find(ZSTD_MAGIC), 0, 0
    while at != -1 and at < end:
        _id, _next, kind, size, compressed = struct.unpack_from("<IIBII", data, at - 17)
        declared = _zstd_declared_size(data, at)
        count, total = count + 1, total + size
        if (at < 17 or kind not in (1, 2, 3) or not 9 <= compressed <= end - at or size > MAX_BLOCK
                or count > MAX_BLOCKS or total > MAX_UNPACKED or (declared is not None and declared > size)):
            raise ValueError("block")
        at = data.find(ZSTD_MAGIC, at + compressed)
    if count == 0:
        raise ValueError("no blocks")


def rofl_info(data: bytes) -> tuple[str, set[str]]:
    """The build (in the header) and the Riot IDs of the ten players (in the metadata at the end) of a .rofl.

    It is a trust boundary: the file is sent by anyone and ends up in the decoder. The structure is read as is
    (header with its build, zstd blocks, and at the end the metadata with its length) and what doesn't add up or
    asks for more memory than a match uses is rejected. ValueError, with a user-friendly message, if it isn't a whole
    replay."""
    if data[:4] != b"RIOT":
        raise ValueError("This is not a League of Legends replay (.rofl).")
    try:
        name_len = data[14]
        build = data[15:15 + name_len].decode("ascii")
        size = struct.unpack("<I", data[-4:])[0]
        end = len(data) - 4 - size
        if not ROFL_BUILD.fullmatch(build) or not 0 < size <= MAX_META or end < 15 + name_len:
            raise ValueError("header")
        _check_blocks(data, end)
        players = json.loads(json.loads(data[end:-4])["statsJson"])
        names = [(p["RIOT_ID_GAME_NAME"], p["RIOT_ID_TAG_LINE"]) for p in players]
        if len(names) != 10 or not all(isinstance(x, str) and len(x) <= MAX_NAME for pair in names for x in pair):
            raise ValueError("players")
        return build, {riot_id(*pair) for pair in names}
    except (ValueError, IndexError, KeyError, TypeError, AttributeError, struct.error, RecursionError) as exc:
        raise ValueError("The replay is incomplete or damaged: download it again from your client.") from exc


def _python() -> str:
    venv = settings.decoder_dir / ".venv"
    windows = venv / "Scripts" / "python.exe"
    return str(windows if windows.exists() else venv / "bin" / "python")


def _exe(build: str) -> Path:
    """The build's exe (`decoder_dir/data/cliente-16.19.821`) or, if it has no folder of its own, that of its patch
    (`cliente-16.19`, which works for hotfixes that don't change the format): the prepared one if needed, otherwise the plain
    one."""
    patch = ".".join(build.split(".")[:2])
    for folder in (settings.decoder_dir / "data" / f"cliente-{build}", settings.decoder_dir / "data" / f"cliente-{patch}"):
        for name in ("descifrado.exe", "League of Legends.exe"):
            if (folder / name).exists():
                return folder / name
    raise FileNotFoundError(f"Patch {patch} can't be read yet: it arrives a few days after the patch.")


DECODER_ERROR = re.compile(r"ERROR\s+(\S+?):\s*(?:\w*Error: )?(.+)")
NO_TABLE = re.compile(r"no hay tabla de tipos para la build (\S+)")


def _why(output: str) -> dict[str, str]:
    """What `cosecha.py` says about each replay that blows up: {replay name: why}, in English.

    Without this, a new build within the same patch (a hotfix: 16.19.821 → 16.19.823) leaves the matches of those
    days out of the analysis with a "could not be decoded" that says nothing."""
    out = {}
    for line in DECODER_ERROR.finditer(output):
        name, reason = line.group(1), line.group(2).strip()
        build = NO_TABLE.search(reason)
        out[name] = (f"This game was played on build {build.group(1)}, which the decoder doesn't read yet."
                         if build else f"The replay could not be decoded ({reason[:160]}).")
    return out


DECODE_TIMEOUT = 240  # s per replay: a real one is 30-60 s, and this is the most one upload can occupy


def _run(cmd: list[str], timeout: int) -> str:
    """Runs the decoder and returns its output. When the deadline expires it kills the whole tree: `cosecha.py` launches child
    processes, and a replay made to hang it can't leave them eating the CPU."""
    posix = os.name == "posix"
    proc = subprocess.Popen(cmd, cwd=settings.decoder_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", start_new_session=posix)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if posix:
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
        proc.communicate()
        raise
    return (out or "") + (err or "")


def decode(versions: dict[str, str], rofls: dict[str, Path]) -> dict[str, str]:
    """{match_id: build}, {match_id: its .rofl} → decodes with `cosecha.py`, in batches by build (each with the exe
    of its build). Returns the ones that couldn't be decoded and why."""
    output = _decoded()
    output.mkdir(parents=True, exist_ok=True)
    by_patch: dict[str, list[str]] = defaultdict(list)
    for match_id, version in versions.items():
        by_patch[".".join(version.split(".")[:3])].append(match_id)
    failures: dict[str, str] = {}
    for patch, ids in by_patch.items():
        try:
            exe = _exe(patch)
        except FileNotFoundError as exc:
            failures |= dict.fromkeys(ids, str(exc))
            continue
        data = exe.parent / "DATA" / "FINAL"  # the names of its build, if downloaded with bajar_exe.py --datos
        with tempfile.TemporaryDirectory(dir=settings.premium_dir) as tmp:
            for match_id in ids:  # cosecha.py walks a folder: this batch's, with links to the replays
                dest = Path(tmp) / f"{replay_name(match_id)}.rofl"
                try:
                    os.link(rofls[match_id], dest)
                except OSError:
                    shutil.copy2(rofls[match_id], dest)
            try:
                text = _run([_python(), "cosecha.py", str(exe), tmp, str(output),
                              "--procesos", str(min(settings.decode_processes, len(ids))),
                              "--datos", str(data if data.exists() else settings.game_data_dir)],
                             DECODE_TIMEOUT * len(ids))
            except subprocess.TimeoutExpired:
                logger.warning("replay_decode_timeout", patch=patch, games=len(ids))
                failures |= dict.fromkeys(ids, "The replay took too long to read.")
                continue
        reasons = _why(text)
        undone = [m for m in ids if not (output / f"{replay_name(m)}.state.csv.gz").exists()]
        if undone:
            logger.warning("premium_decode_failed", patch=patch, games=len(undone), output=text[-2000:])
        failures |= {m: reasons.get(replay_name(m), "The replay could not be decoded.") for m in undone}
    return failures


async def records(player: Player, match_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Match and timeline from Riot for each one, in the harvest format (`ladder_dataset.match_record`) and with the
    player's league: what the WP curve needs. The one that fails is left without a curve, not without analysis."""
    scripts = str(settings.research_dir.parent / "apps" / "api" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from ladder_dataset import match_record  # type: ignore[import-not-found]

    client = riot_client(player.region)
    out: dict[str, dict[str, Any]] = {}
    async with create_secure_session() as session:
        for match_id in match_ids:
            try:
                match = await client.fetch_match(session, match_id)
                timeline = await client.fetch_timeline(session, match_id)
            except Exception as exc:
                logger.warning("premium_timeline_failed", match_id=match_id, error=str(exc))
                continue
            if match and timeline:
                out[match_id] = {**match_record(match, timeline), "tier": player.tier or ""}
    return out


@cache
def _research() -> tuple[Any, Any, Any]:
    """features, coach and premium_references from `research/replays` (imported once, and only in the worker)."""
    folder = str(settings.research_dir / "replays")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import coach  # type: ignore[import-not-found]
    import features  # type: ignore[import-not-found]
    import premium_references  # type: ignore[import-not-found]

    return features, coach, premium_references


def _number(value: Any) -> float | None:
    """The value if it is a real measurement. Impossible values are out (NaN, |x| ≥ 1e7): uninitialised memory that the
    decoder lets through very occasionally and that, in an average over a few matches, swamps everything else."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if abs(value) < 1e7 else None  # NaN doesn't pass either: abs(nan) < 1e7 is false


def analyse(match_id: str, champion: str, record: dict[str, Any] | None) -> dict[str, Any]:
    """A decoded match, for the player who plays `champion`: their row of the features table, their flashes, the
    moments a coach would show them with their minute and place (`coach.analyse`), the gold curves against their opponent
    and, if there is a timeline (`record`), their team's WP every WP_STEP seconds."""
    features, coach, _ = _research()
    base = _decoded() / replay_name(match_id)
    state, events_path = Path(f"{base}.state.csv.gz"), Path(f"{base}.events.json.gz")
    model = settings.research_dir / "ladder" / "data" / "harvest-16.19" / "value" / "model.json"
    with_value = record is not None and model.exists()
    raw: dict[str, Any] = {}
    players, situations, _warning = features.one_game(state, events_path, record,
                                                        model if with_value else None, raw=raw)
    row = next((f for f in players if f["champion"].lower() == champion.lower()), None)
    if row is None:
        raise ValueError(f"{champion} is not in {match_id}.")
    game_entry = {
        "match_id": match_id, "champion": row["champion"], "role": row["position"], "win": bool(row["wins"]),
        "duration": row["duration"],
        "stats": {k: n for k, v in row.items() if (n := _number(v)) is not None},
        "flashes": [{k: f.get(k) for k in ("time", "use", "offensive", "suboptimal", "value")}
                    for f in situations.get("flashes", []) if f.get("champion") == row["champion"]],
        "wp": None,
    } | coach.analyse(raw, record, row["champion"], _openings())
    if (c := raw.get("curve")) is not None:  # the one that one_game already computed to give value to the situations
        blue = c["team"][c["champion"].index(row["champion"])] == "100"
        game_entry["wp"] = [[int(t), round(float(wp if blue else 1 - wp), 4)]
                       for t, wp in zip(c["t"], c["wp"], strict=True) if int(t) % WP_STEP == 0]
    return game_entry


@cache
def _openings() -> dict[str, Any] | None:
    return json.loads(OPENINGS.read_text(encoding="utf-8")) if OPENINGS.exists() else None


@cache
def _reference() -> dict[str, Any]:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def rate(game: dict[str, Any], tier: str | None) -> dict[str, Any]:
    """The 1-to-100 grade of a single match (`rating.score`), with the scale of its league and position: the same as
    `summarize` does with those of a snapshot."""
    _, coach, _ = _research()
    ref = _reference()
    coach.grades([game], ref.get("grades", {}).get(tier if tier in ref["leagues"] else FALLBACK_TIER))
    return game


def summarize(games: list[dict[str, Any]], tier: str | None) -> dict[str, Any]:
    """The player's average in each column of the features table, with their percentile in their league and role, that league's
    median and what those who win and those who lose do on average (what distinguishes whoever wins); and the
    patterns of their matches (`coach.patterns`): what repeats, how much it costs them and how their league does it."""
    _, coach, references = _research()
    ref = _reference()
    role = Counter(g["role"] for g in games).most_common(1)[0][0]
    league = tier if tier in ref["leagues"] else FALLBACK_TIER
    columns = ref["leagues"][league].get(role, {}).get("columns", {})
    metrics = {}
    for column, (p10, p25, p50, p75, p90, _mean, won, lost, _n) in columns.items():
        values = [g["stats"][column] for g in games if g["role"] == role and column in g["stats"]]
        if not values:
            continue
        mean = sum(values) / len(values)
        metrics[column] = {
            "value": round(mean, 3),
            "percentile": round(references.percentile(mean, [p10, p25, p50, p75, p90])),
            "median": p50, "winners": won, "losers": lost,
        }
    own_items = [g for g in games if g["role"] == role]
    # the grade of each match (1-100), with what the moments of players of their league add up to at each position
    coach.grades(games, ref.get("grades", {}).get(league))
    return {"tier": league, "role": role, "games": len(games), "wins": sum(g["win"] for g in games), "metrics": metrics,
            "role_games": len(own_items),
            "patterns": coach.patterns(own_items, columns, league, role, _openings(),
                                       ref["leagues"].get("CHALLENGER", {}).get(role, {}).get("columns"))}
