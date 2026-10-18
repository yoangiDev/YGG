"""What changes on climbing a league, from Gold to Challenger: each feature and each situation of the harvest.

    python research/replays/leagues.py <features folder> [--only-matching] [--json <output.json>]

It prints in markdown the numbers from which research/ladder/league-report-16.19.md comes. Three questions:

1. **what changes with the league**, by position: the mean of the two players of that position in each match against
   the league, with Spearman's rank correlation (one row per match: 1001 per position);
2. **what separates the winner from the loser, and whether that changes with the league**: in each match, winner against
   loser of the same position (same duration, same league, one against the other), and the proportion of matches
   in which the winner has more. The low league (Gold, Platinum) is compared with the high one (Master, GM, Challenger);
3. **the situations**: each concept per match (how many, what proportion of each outcome) against the league.

With `--json` it also saves all the results, whether or not they pass the threshold, which is what the web's
"Stats by rank" tab reads (apps/web/src/features/ranks).

Threshold: |z| >= 4 (p < 1e-4). There are about 700 tests, and with that chance lets not one through (Bonferroni).

Each count goes per 10 minutes **of the stretch it measures**: the laning phase (2-14 min) is a fixed window and
goes as it is; what starts at 14 (side lanes, cost of dying, overgroup) goes per 10 minutes from there on;
the official, per 10 minutes of match. Without this, leagues with longer matches would come out "doing
more of everything".
"""
from __future__ import annotations

import collections
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

LEAGUES = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
LOW, HIGH = {"GOLD", "PLATINUM"}, {"MASTER", "GRANDMASTER", "CHALLENGER"}
POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
Z = 4.0
MAP_SIDE = 14800.0  # the map is symmetric about its centre (7400, 7400): rotated there, a red ward lands where blue would place it
# blue (the river is the diagonal x + z = MAP_SIDE, like RIVER in moments.py)
CELLS = 40  # the wards heatmap: 40 by 40 cells of 370 units, less than a ward's vision radius

LANING = ("lane_", "resources_", "blind_", "vision_", "freeze", "backs", "prio", "departures", "trades", "idle_",
         "jungler_", "finishes_")  # fixed laning-phase window
LATE = ("sidelane_", "dying_")  # from minute 14 to the end
AS_IS = {"level", "plates", "plate_gold", "recall_gold_max", "dying_respawn_mean",
            "dying_gold_per_second", "dying_damage_per_second"}  # they are already means, maxima or things within the 14 min
SKIP = {"team", "duration", "wins", "adds_up", "vision_exempt", "idle_period", "idle_margin",
          "recall_when_max"}


# health and mana are shares of the maximum: outside [0, 1] it is uninitialised memory the emulator read (0.02%
# of trades and 13 players of 8008). That datum is removed, not the match
FRACTIONS = {"health_before", "health_after", "resources_health_mean", "resources_health_minimum", "resources_mana_mean"}


# everything computed, for --json: {"duration", "positions", "winner", "situations", "objectives", "map_wards"}
DATA: dict = {"positions": collections.defaultdict(dict), "winner": collections.defaultdict(dict),
               "situations": collections.defaultdict(dict), "objectives": {}}


def save(t) -> dict:
    means, rho, z = t
    return {"means": [round(m, 4) for m in means], "rho": round(rho, 3), "z": round(float(z), 2)}


def key(name: str) -> str:
    """"CS perdido por back" -> "cs_perdido_por_back": the key with which the web requests each situation."""
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", ascii_).strip("_")


def num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) and abs(x) < 1e7 else None


def read(folder: Path, name: str, only_matching: bool) -> list[dict]:
    with (folder / f"{name}.csv").open(encoding="utf-8") as fh:
        rows = [f for f in csv.DictReader(fh) if not only_matching or f["adds_up"] == "1"]
    for f in rows:
        for c in FRACTIONS & f.keys():
            if (x := num(f[c])) is not None and not -0.01 <= x <= 1.01:
                f[c] = ""
    return rows


def ranks(x: np.ndarray) -> np.ndarray:
    """Ranks with ties averaged, since the league has only seven values."""
    order = x.argsort(kind="mergesort")
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    _, which, how_many = np.unique(x, return_inverse=True, return_counts=True)
    return (np.bincount(which, weights=r) / how_many)[which]


def trend(per_game: dict[str, float], league: dict[str, str]) -> tuple[list[float], float, float] | None:
    """(mean per league, Spearman's rho against the league, z)."""
    ps = [p for p, v in per_game.items() if v is not None and p in league]
    if len(ps) < 50:
        return None
    x = np.array([LEAGUES.index(league[p]) for p in ps], float)
    y = np.array([per_game[p] for p in ps], float)
    if y.std() == 0:
        return None
    rho = float(np.corrcoef(ranks(x), ranks(y))[0, 1])
    means = [float(y[x == i].mean()) if (x == i).any() else float("nan") for i in range(len(LEAGUES))]
    return means, rho, rho * np.sqrt(len(ps) - 1)


def scale(col: str, row: dict) -> float:
    d = float(row["duration"])
    if col in AS_IS or col.startswith(LANING):
        return 1.0
    if col.startswith(LATE):
        return 600 / max(d - 840, 60)
    if col in ("punishments", "punished"):  # the zones are looked at from minute 5
        return 600 / (d - 300)
    return 600 / d


def columns(players: list[dict], position: str) -> list[str]:
    own_items = [f for f in players if f["position"] == position]
    return [c for c in players[0] if c not in SKIP and not c.endswith("_team")
            and sum(num(f[c]) is not None for f in own_items) >= 0.3 * len(own_items)]


def fmt(v: float) -> str:
    return f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}"


def change(means: list[float]) -> str:
    a, b = means[0], means[-1]
    return f"{100 * (b - a) / abs(a):+.0f} %" if a else "—"


def md_row(name: str, t) -> str:
    means, rho, z = t
    return f"| {name} | " + " | ".join(fmt(m) for m in means) + f" | {change(means)} | {rho:+.2f} | {z:+.1f} |"


HEADER = "| | Gold | Plat | Emer | Dia | Master | GM | Chall | Gold→Chall | ρ | z |\n|---|" + "---|" * 10  # noqa: RUF001 (Spearman's rho)


def by_league(players: list[dict], league: dict[str, str]) -> None:
    print("## 1. What changes with the league, by position\n")
    duration = {f["game"]: float(f["duration"]) / 60 for f in players}
    print(HEADER)
    print(md_row("duration (min)", t := trend(duration, league)))
    DATA["duration"] = save(t)
    for position in POSITIONS:
        own_items = [f for f in players if f["position"] == position]
        leave = []
        for c in columns(players, position):
            together = collections.defaultdict(list)
            for f in own_items:
                if (v := num(f[c])) is not None:
                    together[f["game"]].append(v * scale(c, f))
            t = trend({p: sum(v) / len(v) for p, v in together.items()}, league)
            if t:
                DATA["positions"][position][c] = save(t)
            if t and abs(t[2]) >= Z:
                leave.append((abs(t[1]), c, t))
        print(f"\n### {position}\n\n{HEADER}")
        for _, c, t in sorted(leave, reverse=True):
            print(md_row(c, t))


def winner_vs_loser(players: list[dict]) -> None:
    print("\n## 2. What separates the winner from the loser (same position, same game)\n")
    print("Share of games in which the winner has more (not counting ties). 50% means it does not separate.\n")
    print("| position | feature | all | Gold-Plat | Master+ | z of the difference | games |\n|---|---|---|---|---|---|---|")
    pairs = collections.defaultdict(dict)
    for f in players:
        pairs[(f["game"], f["position"])][f["wins"]] = f
    for position in POSITIONS:
        leave = []
        for c in columns(players, position):
            count = {"all": [0, 0], "low": [0, 0], "high": [0, 0]}
            for (_, pu), pair in pairs.items():
                if pu != position or len(pair) < 2:
                    continue
                g, loser = (num(pair[k][c]) for k in ("1", "0"))
                if g is None or loser is None:
                    continue
                g, loser = g * scale(c, pair["1"]), loser * scale(c, pair["0"])
                if g == loser:
                    continue
                groups = ["all"] + (["low"] if pair["1"]["league"] in LOW else
                                      ["high"] if pair["1"]["league"] in HIGH else [])
                for k in groups:
                    count[k][g > loser] += 1
            n, wins = sum(count["all"]), count["all"][1]
            if n < 100:
                continue
            prop = wins / n
            z_all = (wins - n / 2) / np.sqrt(n / 4)
            nb, na = sum(count["low"]), sum(count["high"])
            pb, pa = count["low"][1] / max(nb, 1), count["high"][1] / max(na, 1)
            pp = (count["low"][1] + count["high"][1]) / max(nb + na, 1)
            z_diff = (pa - pb) / np.sqrt(pp * (1 - pp) * (1 / max(nb, 1) + 1 / max(na, 1))) if 0 < pp < 1 else 0.0
            DATA["winner"][position][c] = {"all": round(prop, 4), "low": round(pb, 4), "high": round(pa, 4),
                                           "z": round(float(z_all), 2), "z_diff": round(float(z_diff), 2), "n": n}
            if abs(z_all) >= Z or abs(z_diff) >= 3:
                leave.append((abs(prop - 0.5), position, c, prop, pb, pa, z_diff, n))
        for _, pu, c, prop, pb, pa, z_diff, n in sorted(leave, reverse=True):
            print(f"| {pu} | {c} | {prop:.0%} | {pb:.0%} | {pa:.0%} | {z_diff:+.1f} | {n} |")


def from_blue(f: dict) -> tuple[float, float]:
    """Where a ward falls seen from the blue side: red's, rotated about the centre of the map."""
    x, z = float(f["x"]), float(f["z"])
    return (x, z) if f["team"] == "100" else (MAP_SIDE - x, MAP_SIDE - z)


def ward_map(wards: list[dict]) -> None:
    """Where vision is placed in Grandmaster and Challenger, and in the rest, per team: the share of each group's and
    team's wards that falls in each cell, per ten thousand (z rows, from bottom to top). Nothing rotated:
    blue has its base at the bottom left and red at the top right, so it shows which jungle belongs to whom."""
    groups = {"high": {"GRANDMASTER", "CHALLENGER"}, "rest": set(LEAGUES) - {"GRANDMASTER", "CHALLENGER"}}
    DATA["map_wards"] = {"side": MAP_SIDE, "cells": CELLS}
    print("\n### Ward map\n")
    for name, leagues in groups.items():
        DATA["map_wards"][name] = {}
        for team in ("100", "200"):
            squares = collections.Counter()
            own_items = [f for f in wards if f["league"] in leagues and f["team"] == team]
            for f in own_items:
                i, j = (min(CELLS - 1, max(0, int(float(f[k]) / MAP_SIDE * CELLS))) for k in ("x", "z"))
                squares[j * CELLS + i] += 1
            games = len({f["game"] for f in own_items})
            DATA["map_wards"][name][team] = {
                "wards": len(own_items), "games": games,
                "squares": [round(1e4 * squares[k] / len(own_items)) for k in range(CELLS**2)]}
            print(f"- {name}, team {team}: {len(own_items):,d} wards in {games} games")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def used(prefix):
    return lambda f: float(any(u.startswith(prefix) for u in f["uses"].split("|")))


def gets(what):
    return lambda f: float(what in f["wins"])


def situations(folder: Path, players: list[dict], league: dict[str, str], only: bool) -> None:
    print("\n## 3. The situations, per game\n")
    duration = {f["game"]: float(f["duration"]) for f in players}
    late = {p: max(d - 840, 60) / 600 for p, d in duration.items()}
    from5 = {p: (d - 300) / 600 for p, d in duration.items()}
    # (table, name, filter, value per row, aggregate): "mean" of the match's rows, or "count" of
    # rows divided by the stretch (None = fixed laning-phase window)
    M = [
        ("backs", "backs with the cannon on the way (%)", None, lambda f: f["kind"].startswith("cannon") and "on the way" in f["kind"], "mean"),
        ("backs", "backs after the cannon (%)", None, lambda f: "next" in f["kind"], "mean"),
        ("backs", "backs with a normal wave (%)", None, lambda f: f["kind"] == "normal wave", "mean"),
        ("backs", "backs without clearing the wave (%)", None, lambda f: f["kind"].startswith("without"), "mean"),
        ("backs", "CS lost per back", None, lambda f: num(f["cs_lost"]), "mean"),
        ("prio", "crashes per game (up to 15)", None, None, "count"),
        ("prio", "crash with no use at all (%)", None, lambda f: f["uses"] == "", "mean"),
        ("prio", "crash → goes back to base (%)", None, used("goes back to base"), "mean"),
        ("prio", "crash → goes into the fog (%)", None, used("goes into the fog"), "mean"),
        ("prio", "crash → harass under tower (%)", None, used("harass"), "mean"),
        ("prio", "crash → rotates to another lane (%)", None, used("broken"), "mean"),
        ("prio", "crash → vision (%)", None, used("visi"), "mean"),
        ("prio", "crash → several uses (%)", None, lambda f: len([u for u in f["uses"].split("|") if u]) >= 2, "mean"),
        ("prio", "seconds in the fog after the crash", None, lambda f: num(f["hidden"]), "mean"),
        ("prio", "CS lost per crash", None, lambda f: num(f["cs_lost"]), "mean"),
        ("clashes", "crashed waves per game", None, None, "count"),
        ("clashes", "of them, stacks of 2+ waves (%)", None, lambda f: num(f["stack"]), "mean"),
        ("clashes", "bounce that comes back (%)", None, lambda f: f["bounce"] != "", "mean"),
        ("clashes", "champions who reach the bounce", lambda f: f["bounce"] != "", lambda f: num(f["arrive"]), "mean"),
        ("clashes", "CS lost per clash", None, lambda f: num(f["cs_lost"]), "mean"),
        ("accumulations", "slow pushes per game", None, None, "count"),
        ("accumulations", "slow push that clashes (%)", None, lambda f: f["clash"] != "", "mean"),
        ("accumulations", "slow push that freezes the rival (%)", None, lambda f: f["freezes"] != "", "mean"),
        ("accumulations", "slow push that the rival eats (%)", None, lambda f: f["come"] != "", "mean"),
        ("accumulations", "peak of minion advantage", None, lambda f: num(f["peak"]), "mean"),
        ("freezes", "freezes per game", None, None, "count"),
        ("freezes", "seconds it lasts", None, lambda f: num(f["until"]) - num(f["since"]), "mean"),
        ("freezes", "CS it denies the rival", None, lambda f: num(f["rival_cs_lost"]), "mean"),
        ("trades", "trades per game (rows per champion)", None, None, "count"),
        ("trades", "seconds it lasts", None, lambda f: num(f["lasts"]), "mean"),
        ("trades", "damage per champion and trade", None, lambda f: num(f["damage"]), "mean"),
        ("trades", "abilities per champion and trade", None, lambda f: num(f["abilities"]), "mean"),
        ("trades", "burns a summoner (%)", None, lambda f: num(f["summoners"]) > 0, "mean"),
        ("trades", "ends up dying (%)", None, lambda f: num(f["died"]), "mean"),
        ("trades", "health at the end", None, lambda f: num(f["health_after"]), "mean"),
        ("departures", "lane departures per game", None, None, "count"),
        ("departures", "leaves with the wave pushed (%)", None, lambda f: num(f["won"]), "mean"),
        ("departures", "gets something (%)", None, lambda f: f["wins"] != "", "mean"),
        ("departures", "→ a kill they hit in (%)", None, gets("kills"), "mean"),
        ("departures", "→ a camp or objective (%)", None, gets("falls "), "mean"),
        ("departures", "→ a summoner burned (%)", None, gets("burns"), "mean"),
        ("departures", "→ a deep ward (%)", None, gets("ward at"), "mean"),
        ("departures", "leaves accompanied (%)", None, lambda f: f["together"] != "", "mean"),
        ("departures", "CS lost per departure", None, lambda f: num(f["cs_lost"]), "mean"),
        ("departures", "mid departures per game", lambda f: f["position"] == "MIDDLE", None, "count"),
        ("departures", "support departures per game", lambda f: f["position"] == "UTILITY", None, "count"),
        ("jungler_windows", "times the jungler shows up", None, None, "count"),
        ("jungler_windows", "shows up and gets something (%)", None, lambda f: f["wins"] != "", "mean"),
        ("jungler_windows", "→ kill (%)", None, gets("kills"), "mean"),
        ("jungler_windows", "→ summoner burned (%)", None, gets("burns"), "mean"),
        ("jungler_windows", "→ the rival laner retreats or goes back (%)", None, lambda f: "retreats" in f["wins"] or "goes back to base" in f["wins"], "mean"),
        ("jungler_windows", "with camps left standing (%)", None, lambda f: f["standing"] != "", "mean"),
        ("sidelanes", "sidelane turns (per 10 min from 14)", None, None, "late"),
        ("sidelanes", "how much it pushes per turn", None, lambda f: num(f["push"]), "mean"),
        ("sidelanes", "crashes the wave (%)", None, lambda f: num(f["clash"]) > 0, "mean"),
        ("sidelanes", "rivals not located while pushing", None, lambda f: num(f["uncounted"]), "mean"),
        ("sidelanes", "with the ult ready (%)", None, lambda f: num(f["ulti"]), "mean"),
        ("sidelanes", "the rival answers (%)", None, lambda f: f["answers"] != "", "mean"),
        ("sidelanes", "dies on the turn (%)", None, lambda f: num(f["died"]), "mean"),
        ("sidelanes", "dies pushing with 3+ rivals unlocated (%)", lambda f: num(f["uncounted"]) >= 3, lambda f: num(f["died"]), "mean"),
        ("sidelanes", "CS per turn", None, lambda f: num(f["cs"]), "mean"),
        ("side_balance", "sidelanes abandoned (per 10 min from 14)", None, None, "late"),
        ("side_balance", "gold lost per abandonment", None, lambda f: num(f["gold_lost"]), "mean"),
        ("side_balance", "balance against the rival", None, lambda f: num(f["balance"]), "mean"),
        ("side_balance", "wave that piles up meanwhile", None, lambda f: num(f["piles"]), "mean"),
        ("overgroup", "overgroups (per 10 min from 14)", None, None, "late"),
        ("overgroup", "minions lost per overgroup", None, lambda f: num(f["minions"]), "mean"),
        ("punishments", "punished facechecks (per 10 min from 5)", None, None, "from5"),
        ("punishments", "the punished one dies (%)", None, lambda f: num(f["died"]), "mean"),
        ("setups", "seconds of lead on arriving", None, lambda f: num(f["arrives"]), "mean"),
        ("setups", "seconds of ward in the area", None, lambda f: num(f["ward_seconds"]), "mean"),
        ("setups", "seconds of ward in the pit", None, lambda f: num(f["in_the_pit"]), "mean"),
        ("setups", "control wards in the area", None, lambda f: num(f["control_wards"]), "mean"),
        ("setups", "punished facechecks in the setup", None, lambda f: num(f["punishments"]), "mean"),
        ("setups", "players who prepare it", None, lambda f: num(f["they_prepare_it"]), "mean"),
        ("setups", "share of the jungler/support duo's work", None, lambda f: num(f["duo"]), "mean"),
        ("recalls", "recalls per player and game", None, None, "player"),
        ("recalls", "cancelled recalls per player and game", lambda f: f["cancelled"] == "1", None, "player"),
        ("recalls", "cancelled recall (%)", None, lambda f: num(f["cancelled"]), "mean"),
        ("recalls", "recalls cut short by a rival per player and game", lambda f: f["cut_short"] == "1", None, "player"),
        ("recalls", "of the cancelled, cut short by a rival (%)", lambda f: f["cancelled"] == "1",
         lambda f: num(f["cut_short"]), "mean"),
        # 2000 is roughly one screen: the enemy you see coming. At 1200 it rises the same but it is a third of them
        ("recalls", "of the cancelled, with a rival on screen (%)", lambda f: f["cancelled"] == "1",
         lambda f: (num(f["rival_near"]) or 1e9) <= 2000, "mean"),
        ("recalls", "cancelled with a rival on screen per player and game",
         lambda f: f["cancelled"] == "1" and (num(f["rival_near"]) or 1e9) <= 2000, None, "player"),
        ("wards", "wards on the rival half of the map (%)", None, lambda f: sum(from_blue(f)) > MAP_SIDE, "mean"),
    ]
    tables = {n: read(folder, n, only) for n in {m[0] for m in M} | {"setups"}}
    games = set(league)
    current = None
    for table, name, filter_, value, how in M:
        if table != current:
            print(f"\n### {table}\n\n{HEADER}")
            current = table
        rows = [f for f in tables[table] if filter_ is None or filter_(f)]
        groups = collections.defaultdict(list)
        for f in rows:
            groups[f["game"]].append(f)
        if how == "mean":
            by = {p: mean([None if (v := value(f)) is None else float(v) for f in fs]) for p, fs in groups.items()}
        else:
            stretch = {"count": lambda p: 1.0, "late": late.get, "from5": from5.get,
                     "player": lambda p: 10.0}[how]
            by = {p: len(groups.get(p, [])) / stretch(p) for p in games}
        t = trend(by, league)
        if t:
            DATA["situations"][table][key(name)] = save(t)
            print(md_row(name + ("" if abs(t[2]) >= Z else " ·"), t))
    print("\n`·` = does not pass the |z| ≥ 4 threshold: it does not change with the league, or it cannot be stated.")
    ward_map(tables["wards"])

    # whoever sets up better, do they take it? Each objective has one row per team
    print("\n### Does whoever prepares the objective better take it?\n")
    print("| prepared more… | Gold-Plat | Emer-Dia | Master+ | all |\n|---|---|---|---|---|")
    objectives = collections.defaultdict(list)
    for f in tables["setups"]:
        objectives[(f["game"], f["objective"], f["time"])].append(f)
    for name, field in (("seconds of ward in the area", "ward_seconds"), ("lead on arriving", "arrives"),
                          ("control wards", "control_wards"), ("punished facechecks", "punishments"),
                          ("presence", "presence")):
        count = collections.defaultdict(lambda: [0, 0])
        for fs in objectives.values():
            if len(fs) != 2 or num(fs[0][field]) is None or num(fs[1][field]) is None:
                continue
            a, b = sorted(fs, key=lambda f: num(f[field]))
            if num(a[field]) == num(b[field]) or a["takes_it"] == b["takes_it"]:
                continue
            group = "low" if b["league"] in LOW else "high" if b["league"] in HIGH else "mean"
            for k in (group, "all"):
                count[k][int(b["takes_it"])] += 1
        DATA["objectives"][field] = {k: {"wins": c[1], "n": sum(c)} for k, c in count.items()}
        print(f"| {name} | " + " | ".join(f"{c[1] / sum(c):.0%} ({sum(c)})" if sum(c) else "—"
                                          for c in (count[k] for k in ("low", "mean", "high", "all"))) + " |")


def main() -> None:
    assert list(ranks(np.array([3.0, 1.0, 3.0]))) == [1.5, 0.0, 1.5]  # ties, averaged
    sys.stdout.reconfigure(encoding="utf-8")  # redirected to a file, Windows would write in cp1252
    folder = Path(sys.argv[1])
    only = "--only-matching" in sys.argv
    players = read(folder, "players", only)
    league = {f["game"]: f["league"] for f in players}
    assert set(league.values()) <= set(LEAGUES), set(league.values()) - set(LEAGUES)
    print(f"# Numbers per league · {len(league)} games · "
          + ", ".join(f"{k} {v}" for k, v in collections.Counter(league.values()).items()) + "\n")
    by_league(players, league)
    winner_vs_loser(players)
    situations(folder, players, league, only)
    if "--json" in sys.argv:
        DATA["games"] = collections.Counter(league.values())
        path = Path(sys.argv[sys.argv.index("--json") + 1])
        path.write_text(json.dumps(DATA, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
