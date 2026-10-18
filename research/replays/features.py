"""The harvested matches turned into rows a model can eat.

    python research/replays/features.py <harvest folder> <output folder> [--processes N]
                                      [--leagues research/ladder/data/harvest-16.19/matches.jsonl.gz
                                       [--value research/ladder/data/harvest-16.19/value/model.json]]

`moments.py` measures concepts and counts them on screen, which is good for looking at one match. To learn from
a thousand, rows are needed, and in two different forms because they are two different questions:

- **`players.csv`**, one row per (match, player): the aggregate features of how they played, plus their result.
  It is the table of "what distinguishes whoever wins in this position": each column is a measure comparable across
  champions and matches, and the label (`wins`) comes from the .rofl itself. With `--leagues`, each row (also
  those of situations) carries the match's league, which the .rofl doesn't bring: that way one can also ask
  what distinguishes a Challenger from a Gold, not only whoever wins from whoever loses. And all carry `adds_up`:
  whether the match matches its statsJson, to train with all and without those that don't (see `adds_up()`).
- **a table per concept**, one row per situation: each freeze, each wave crash with what was
  done with the prio, each lane departure, each side-lane turn, each punishment, each objective
  setup. It is the table of "what does one of these played well look like", and it is the one that lets the threshold be learned
  instead of set by hand. A situation doesn't depend on the champion: there is nothing here that is "Kha'Zix's W
  against Hwei's E", but "wave crashed at 6:11, with prio, used to punish under tower".

With `--value` (and `--leagues`, where the timeline also comes from), each situation also carries how much it is worth —the
change in its team's WP per second— and whose it is, and `roam_decisions.csv` and `flash_decisions.csv` come out
to compare decisions in the same game state: see `value.py` and `value.md`. That triples the time.

Both come out of the same pass, and it is cheap: 8 matches in 6 s with 4 processes, so **a thousand is
about 13 minutes and 30 MB**. That matters more than it seems: redoing the tables when a concept changes or
another is added doesn't require touching the .rofl again, which take 8 hours. The harvest is done once; this, as many times
as needed.
"""

from __future__ import annotations

import collections
import csv
import gzip
import json
import os
import shutil
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import moments as M
import value as V
import wp_per_second as W

# What the .rofl gives of each player without anyone computing it: the result and the official totals.
OFFICIAL = {
    "kills": "CHAMPIONS_KILLED", "deaths": "NUM_DEATHS", "assists": "ASSISTS",
    "cs": "MINIONS_KILLED", "cs_jungle": "NEUTRAL_MINIONS_KILLED", "gold": "GOLD_EARNED",
    "level": "LEVEL", "damage": "TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", "damage_received": "TOTAL_DAMAGE_TAKEN",
    "vision": "VISION_SCORE", "wards": "WARD_PLACED", "wards_killed": "WARD_KILLED",
    "cc_to_others": "TIME_CCING_OTHERS", "plates": "Missions_TurretPlatesDestroyed",
    "plate_gold": "Missions_GoldFromTurretPlatesTaken",
}
CONCEPTS = ("freezes", "backs", "clashes", "accumulations", "prio", "trades", "departures",
             "sidelanes", "overgroup", "side_balance", "punishments", "setups", "jungler_windows", "recalls", "wards",
             "fights", "flashes", "roams", "roam_decisions", "flash_decisions", "camp_pairs", "plays", "watchers",
             "sieges", "plates")


def _num(x):
    """To a number if possible, which is how a model wants it."""
    try:
        return int(x)
    except (TypeError, ValueError):
        try:
            return float(x)
        except (TypeError, ValueError):
            return x


def aplana(row: dict) -> dict:
    """A situation with each field in a cell: the lists of things keep their size and the ones of
    loose values are joined with `|`, which is what fits in a CSV without losing what it was about."""
    out = {}
    for key, value in row.items():
        if isinstance(value, dict):
            out[key] = len(value)
        elif isinstance(value, (list, tuple)):
            if (value and isinstance(value[0], (dict, list, tuple))) or len(value) > 8:
                out[key] = len(value)
            else:
                out[key] = "|".join(str(x) for x in value)
        elif isinstance(value, bool):
            out[key] = int(value)
        else:
            out[key] = value
    return out


def trade_situations(changes: list[dict]) -> list[dict]:
    """A trade brings several champions inside; the model wants one row per champion taking part."""
    out = []
    for t in changes:
        died = {c for side in t["sides"].values() for c in side["died"]}
        for side in t["sides"].values():
            for champion, d in side["champions"].items():
                if not d["damage"] and not d["abilities"]:
                    continue
                out.append({
                    "lane": t["lane"], "time": round(t["since"], 1),
                    "lasts": round(t["until"] - t["since"], 1), "champion": champion,
                    "starts": int(t["starts"] == champion), "damage": round(d["damage"] or 0),
                    "abilities": d["abilities"], "summoners": len(d["summoners"]),
                    "health_before": round(d["health_before"] or 0, 3), "health_after": round(d["health_after"] or 0, 3),
                    "died": int(champion in died), "dying": len(died),
                    # the wave isn't always known: if the trade falls where there are no minions, it is left blank
                    "wave": round(t["wave"], 3) if t["wave"] is not None else ""})
    return out


def setup_situations(objectives: list[dict]) -> list[dict]:
    """An objective is set up by teams, so the comparable unit is (objective, team): how much each arrived
    on time at the pit, how much vision they had of the area and the river, and what share was placed by the duo."""
    out = []
    for o in objectives:
        for team, d in o["sides"].items():
            out.append({
                "objective": o["objective"], "time": round(o["falls"], 1), "zone": o["zone"], "team": team,
                "takes_it": int(o["takes_it"] == team), "arrives": d["arrives"],
                "ward_seconds": d["ward_seconds"], "in_the_pit": d["in_the_pit"],
                "in_the_river": d["in_the_river"], "presence": d["presence"],
                "control_wards": d["control_wards"], "punishments": d["punishments"],
                "they_prepare_it": len(d["work"]), "contribution_total": sum(d["work"].values()),
                "duo": d["duo"] if d["duo"] is not None else ""})
    return out


def adds_up(events: dict, rows: dict) -> int:
    """1 if the match matches its own statsJson, like the harvest when it doesn't mark it with `!!`: each player's
    deaths spot on and CS within 3% of the total (and at 15 for each player).

    No match that doesn't match is thrown out, because that would remove from the sample those of Akshan, Sion and company.
    The column is for training with all and without these: if the conclusions don't change, the noise from
    odd mechanics doesn't weigh."""
    deaths = collections.Counter(e["net_id"] for e in events["events"] if e["type"] == "Death")
    stats = events["stats"]
    if [deaths[p["net_id"]] for p in events["players"]] != [int(s["NUM_DEATHS"]) for s in stats]:
        return 0
    cs = [float(rows[p["champion"]][-1]["cs"] or 0) if rows.get(p["champion"]) else 0.0
          for p in events["players"]]
    expected = [int(s["MINIONS_KILLED"]) for s in stats]
    error = abs(sum(cs) - sum(expected)) / max(sum(expected), 1)
    return int(error <= 0.03 and all(abs(a - b) <= 15 for a, b in zip(cs, expected)))


def one_game(state: Path, events_path: Path, record: dict | None = None,
                model: Path | None = None, raw: dict | None = None) -> tuple[list[dict], dict[str, list[dict]], str]:
    """(one row per player, the situations per concept, warning) of a harvested match.

    With its `record` (timeline and league, from `wp_per_second.records`) and the `model` of `value.py`, each situation
    also carries its value and whose it is (`value.annotate`), and the support's and flash's decision tables
    come out (`value.roam_decisions` and `value.flash_decisions`). If that fails, the match comes out without them and the
    warning says why.

    `raw`, if passed, is filled with what the rows summarise, unflattened and with their time and place (the
    events, the table, the fights, the concepts with their value, the WP curve…): from there `coach.py` takes a player's
    moments without computing anything again."""
    with M.open_file(events_path) as fh:
        events = M.drop_revived(json.load(fh))
    rows = M.read_state(state)
    waves = M.lane_waves(events)
    game = state.name.split(".")[0]
    ok = adds_up(events, rows)

    clashes = M.stacks(events, waves, rows)
    punishments_by_zone = M.zones(events, waves, rows)
    punishments = [c for z in punishments_by_zone for c in z["punishments"]]
    fight_list = M.fights(events, rows)
    flash_list = M.flashes(events, rows, fight_list)
    roam_list, by_marksman = M.roams(events, rows)
    show = M.show_up(events, waves, rows)
    idle = M.idle_jungle(events, rows, until=840)
    paired = M.camp_pairs(events, rows, fight_list)
    play_list = M.plays(events, waves, rows, fight_list, show, idle)
    watchers = M.vision(events, waves, rows, until=None)  # the whole match's wards (the 14 ones, further down)
    # the turrets' health, if the match was harvested with it: the stretches when they get hit and who was in front
    siege_list = M.sieges(events, waves, rows, M.read_turrets(state))
    # the laning phase's plates, from Riot's timeline (`record`): cheap gold and what most predicts the lane
    plate_list = M.plates(events, record)
    support_items = M.support_item(events, rows)
    cold, recall_list = M.freezes(events, waves, rows), M.recalls(events, rows)
    concepts = {
        "freezes": cold,
        "backs": M.backs(events, rows, waves, clashes=clashes, cold=cold),
        "clashes": clashes,
        "accumulations": M.accumulations(events, waves, rows, clashes=clashes, cold=cold),
        "prio": M.payoff(events, waves, rows, clashes),
        "trades": trade_situations(trade_list := M.trades(events, waves, rows)),
        "departures": M.departures(events, waves, rows),
        "sidelanes": M.sidelanes(events, waves, rows),
        "overgroup": M.overgroup(events, waves, rows),
        "side_balance": M.side_balance(events, waves),
        "punishments": punishments,
        "setups": setup_situations(objectives := M.setups(events, waves, rows, punishments)),
        "jungler_windows": [dict(v, jungler=j["jungler"], team=j["team"]) for j in show for v in j["windows"]],
        "recalls": recall_list,
        # where each ward lands, for the heatmap (leagues.py rotates it to the blue side)
        "wards": [{"time": round(t0, 1), "x": round(x), "z": round(z), "team": team, "champion": who}
                  for t0, _t1, (x, z), team, who in M._wards(events)],
        "fights": [{k: v for k, v in f.items() if k not in ("damage", "taken")} for f in fight_list],
        "flashes": flash_list,
        "roams": roam_list,
        # the camps of a sector left without their pair, with what the jungler did instead of clearing it
        "camp_pairs": [dict(r, jungler=j, team=d["team"], time=r["t"]) for j, d in paired.items() for r in d["detail"]],
        "plays": [dict(x, time=x["since"]) for x in play_list],
        # each ward of each support over the whole match: when it was placed, what was risked and what it gave
        "sieges": [dict(a, time=a["since"]) for a in siege_list],
        "plates": plate_list,
        "watchers": [{"champion": v["champion"], "team": v["team"], "time": round(w["when"], 1),
                    **{k: w[k] for k in ("kind", "x", "z", "moment", "risk", "in_fight", "in_sight", "passed", "alone",
                                         "uncounted", "costs_it", "seconds", "to_jungler", "lives", "sweep",
                                         "past_the_lane", "depth")}}
                   for v in watchers if v["position"] == "UTILITY" for w in v["wards"]],
    }
    notice, curve = "", None
    if record is not None and model is not None:  # without a model there is no value, but the timeline does carry the plates
        try:
            curve = V.curve(record, events, state, V.coefficients(model))
            V.annotate(concepts, curve, events, rows)
            concepts["roam_decisions"] = V.roam_decisions(curve, events, rows)
            concepts["flash_decisions"] = V.flash_decisions(curve, events, rows, fight_list, flash_list)
        except Exception as e:  # without value, but with everything else
            notice = f"no value: {type(e).__name__}: {e}"
    situations = {name: [dict(aplana(x), game=game, adds_up=ok) for x in items]
                   for name, items in concepts.items()}

    # ── one row per player ─────────────────────────────────────────────────────────────────────────
    by_champion = {c: {} for c in (p["champion"] for p in events["players"])}
    team_of = {p["champion"]: p["team"] for p in events["players"]}

    def split(items, key="champion", prefix=""):
        for r in items:
            if (c := r.get(key)) in by_champion:
                by_champion[c] |= {f"{prefix}{k}": v for k, v in r.items() if k != key}

    exposure = M.exposure(events, waves, rows)
    split(M.gold_in_lane(events, rows, record), prefix="lane_")
    split(M.resources_in_lane(events, rows), prefix="resources_")
    split(exposure, prefix="blind_")
    split(M.vision(events, waves, rows), prefix="vision_")
    split(M.cost_of_dying(events, rows), prefix="dying_")
    split(M.finishes(events, waves, rows), prefix="finishes_")
    split(M.health_before_back(events, rows, recall_list=recall_list))
    split(by_marksman, prefix="roam_")
    for jungler, r in idle.items():
        if jungler in by_champion:
            by_champion[jungler] |= {f"idle_{k}": v for k, v in r.items()}
    for jungler, r in M.jungler_recalls(events, rows).items():
        if jungler in by_champion:
            by_champion[jungler] |= {f"recall_{k}": v for k, v in r.items()}
    for j in show:
        in_lane = [v for v in j["windows"] if v["near"]]  # with an enemy laner in range: the rest is a ward that sees it
        by_champion[j["jungler"]] |= {
            "jungler_invisible": j["invisible"], "jungler_visible": j["visible"],
            "jungler_streak": j["streak_invisible"], "jungler_shows_up": len(j["windows"]),
            "jungler_in_lane": len(in_lane), "jungler_taking_nothing": sum(not v["wins"] for v in in_lane)}
    for jungler, d in paired.items():
        by_champion[jungler] |= {f"pairs_{k}": d[k] for k in ("clears", "paired", "broken", "stolen", "unpaired")}
        own_rows = [x for x in play_list if x["jungler"] == jungler and not x["invaded"]]  # the ones they choose
        by_champion[jungler] |= {
            "plays": len(own_rows), "plays_good_ones": sum(x["verdict"] == "good" for x in own_rows),
            "plays_bad_ones": sum(x["verdict"] == "bad" for x in own_rows),
            "plays_value": sum(x["value"] for x in own_rows), "plays_cost_gold": sum(x["gold_cost"] for x in own_rows),
            "plays_with_camps": sum(bool(x["camps"]) for x in own_rows)}
    minutes = max(1.0, events["game_length"] / 60)
    for v in watchers:  # the whole match's vision, everyone's; the item's, only the support's
        w = v["wards"]
        by_champion[v["champion"]] |= {
            "guard_wards": len(w), "guard_wards_10": 10 * len(w) / minutes,
            "guard_useful_share": sum(bool(x["reveals"]) for x in w) / len(w) if w else "",
            "guard_info_per_ward": sum(x["seconds"] for x in w) / len(w) if w else "",
            "guard_to_jungler_10": 10 * sum(x["to_jungler"] for x in w) / minutes,
            "guard_objective_share": sum(x["moment"] == "objective" for x in w) / len(w) if w else "",
            "guard_loose_share": sum(x["moment"] == "loose" for x in w) / len(w) if w else "",
            "guard_risk_high_share": sum(x["risk"] == "high" and not x["in_fight"] for x in w) / len(w) if w else "",
            "guard_costs_it": sum(x["costs_it"] and not x["in_fight"] for x in w),
            "guard_sweeps_share": sum(x["sweep"] for x in w) / len(w) if w else ""}
    for d in support_items:
        by_champion[d["champion"]] |= {
            "support_item_since": d["since"] if d["since"] is not None else "", "support_item_seconds": d["seconds"],
            "support_item_empty": d["empty"], "support_item_empty_share": d["empty_share"] if d["empty_share"] is not None else "",
            "support_item_wards": d["wards"], "support_item_trips": d["trips"], "support_item_charges_wasted": d["charges_wasted"],
            "support_item_wasted_per_trip": d["charges_wasted"] / d["trips"] if d["trips"] else "",
            "control_bought": d["control_bought"], "control_placed": d["control_placed"],
            "control_placed_10": 10 * d["control_placed"] / minutes, "sweeps_10": 10 * d["sweeps"] / minutes}

    # what is counted: how many situations of each type they star in, and how they turned out
    accounts = {
        "freezes": [c for c in concepts["freezes"]],
        "backs": concepts["backs"], "prio": concepts["prio"],
        "departures": concepts["departures"], "sidelanes": concepts["sidelanes"],
        "trades": concepts["trades"],
    }
    for champion, row in by_champion.items():
        own_items = {n: [x for x in v if champion in (x.get("champion"), *(x.get("who") or []))]
                 for n, v in accounts.items()}
        row["freezes"] = len(own_items["freezes"])
        row["freeze_seconds"] = round(sum(x["until"] - x["since"] for x in own_items["freezes"]))
        row["freeze_cs_denied"] = sum(x["rival_cs_lost"] for x in own_items["freezes"])
        row["backs"] = len(own_items["backs"])
        row["backs_cs_lost"] = sum(x["cs_lost"] for x in own_items["backs"])
        # the verdict goes by where the wave is on pressing it (moments.wave_on_return), not by what is lost
        row["backs_good"] = sum(x["verdict"] == "good" for x in own_items["backs"])
        row["backs_bad"] = sum(x["verdict"] == "bad" for x in own_items["backs"])
        row["prio"] = len(own_items["prio"])
        row["prio_unused"] = sum(not x["uses"] for x in own_items["prio"])
        row["prio_cs_lost"] = sum(x["cs_lost"] for x in own_items["prio"])
        row["departures"] = len(own_items["departures"])
        row["departures_no_wave"] = sum(not x["won"] for x in own_items["departures"])
        row["departures_cs_lost"] = sum(x["cs_lost"] for x in own_items["departures"])
        row["departures_taking_nothing"] = sum(not x["wins"] for x in own_items["departures"])
        row["sidelane_turns"] = len(own_items["sidelanes"])
        row["sidelane_seconds"] = sum(x["until"] - x["since"] for x in own_items["sidelanes"])
        row["sidelane_cs"] = sum(x["cs"] for x in own_items["sidelanes"])
        row["sidelane_to_tower"] = sum(x["clash"] for x in own_items["sidelanes"])
        row["sidelane_deaths"] = sum(x["died"] for x in own_items["sidelanes"])
        row["trades"] = len(own_items["trades"])
        row["trades_dies"] = sum(x["died"] for x in own_items["trades"])
        row["trades_summoners"] = sum(x["summoners"] for x in own_items["trades"])
        row["punishments"] = sum(champion in c["catchers"] for c in punishments)
        row["punished"] = sum(champion == c["victim"] for c in punishments)
        # what they contribute to setting up objectives: wards, control and punishments in the zone in the minute and a half before
        own_flash = [f for f in flash_list if f["champion"] == champion]
        row["flashes"] = len(own_flash)
        for use in ("objective", "teamfight", "skirmish", "out of fight"):
            row[f"flash_{use.replace(' ', '_')}"] = sum(f["use"] == use for f in own_flash)
        row["flash_offensive"] = sum(f["offensive"] for f in own_flash)
        row["flash_suboptimal"] = sum(f["suboptimal"] for f in own_flash)
        mine_list = [f for f in fight_list if champion in f["who"]]
        row["fights"] = len(mine_list)
        row["outnumbered_fights"] = sum(f["lower"] == team_of[champion] for f in mine_list)
        tfs = [f for f in mine_list if f["teamfight"]]
        row["teamfights"] = len(tfs)
        row["teamfight_damage"] = round(sum(f["damage"].get(champion, 0) for f in tfs))
        row["teamfight_damage_mean"] = round(row["teamfight_damage"] / len(tfs)) if tfs else ""
        row["setups"] = sum(side["work"].get(champion, 0) for o in objectives for side in o["sides"].values())

    players = []
    for p, official in zip(events["players"], events["stats"]):
        row = {"game": game, "champion": p["champion"], "position": p["position"],
                "team": p["team"], "duration": round(events["game_length"]),
                "wins": int(official.get("WIN") == "Win"), "adds_up": ok}
        row |= {name: _num(official.get(key, 0)) for name, key in OFFICIAL.items()}
        row |= {k: (int(v) if isinstance(v, bool) else v)
                 for k, v in by_champion[p["champion"]].items()
                 if not isinstance(v, (list, tuple, dict))}
        players.append(row)
    if raw is not None:
        raw |= {"events": events, "rows": rows, "waves": waves, "concepts": concepts, "objectives": objectives,
                  "fights": fight_list, "show_up": show, "idle": idle, "exposure": exposure,
                  "curve": curve, "camp_pairs": paired, "plays": play_list, "watchers": watchers, "support_item": support_items,
                  "fights": fight_list, "trades": trade_list, "sieges": siege_list,
                  "plates": plate_list}
    return players, situations, notice


def task(pair: tuple) -> dict:
    state, events, *value = pair
    try:
        players, situations, notice = one_game(Path(state), Path(events), *value)
        return {"players": players, "situations": situations, "notice": notice,
                "game": Path(state).name.split(".")[0]}
    except Exception:  # a strange match can't stop a thousand
        return {"game": Path(state).name.split(".")[0],
                "error": traceback.format_exc(limit=3).strip().split("\n")[-1]}


def write(path: Path, rows: list[dict]) -> None:
    """CSV with the union of the columns of all the rows, since not all matches carry the same."""
    if not rows:
        return
    columns = list(dict.fromkeys(k for f in rows for k in f))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, restval="")
        writer.writeheader()
        # floats with four decimals: what comes after is floating-point noise, not measurement
        writer.writerows({k: round(v, 4) if isinstance(v, float) else v for k, v in f.items()} for f in rows)


def merge_files(path: Path, parts: list[Path]) -> tuple[int, int]:
    """The CSVs of `parts` into a single one, with the union of their columns: (rows, columns)."""
    columns: dict[str, None] = {}
    for p in parts:
        with p.open(newline="", encoding="utf-8") as fh:
            columns |= dict.fromkeys(next(csv.reader(fh)))
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), restval="")
        writer.writeheader()
        for p in parts:
            with p.open(newline="", encoding="utf-8") as g:
                for row in csv.DictReader(g):
                    writer.writerow(row)
                    rows += 1
    return rows, len(columns)


def main() -> None:
    harvest, output = Path(sys.argv[1]), Path(sys.argv[2])
    rest = sys.argv[3:]
    processes = (int(rest[rest.index("--processes") + 1]) if "--processes" in rest
                else max(1, (os.cpu_count() or 4) // 2))
    output.mkdir(parents=True, exist_ok=True)

    pairs = []
    for state in sorted(harvest.glob("*.state.csv*")):
        game = state.name.split(".")[0]
        events = next(iter(harvest.glob(f"{game}.events.json*")), None)
        if events:
            pairs.append((str(state), str(events)))
    print(f"{len(pairs)} games harvested · {processes} processes")
    if "--value" in rest:  # the timeline comes from the same file as the league
        model = Path(rest[rest.index("--value") + 1])
        records = W.records(Path(rest[rest.index("--leagues") + 1]), {Path(e).name.split(".")[0] for e, _ in pairs})
        pairs = [(e, v, records.get(Path(e).name.split(".")[0]), model) for e, v in pairs]
        print(f"value with {model}: {sum(p[2] is not None for p in pairs)} games with timeline", flush=True)

    leagues = None
    if "--leagues" in rest:  # match_id EUW1_123 is replay EUW1-123
        with gzip.open(rest[rest.index("--leagues") + 1], "rt", encoding="utf-8") as fh:
            leagues = {(m := json.loads(line))["match_id"].replace("_", "-"): m["tier"] for line in fh}

    # The situations are written in batches and joined at the end: those of five thousand matches are millions of
    # rows, and they don't fit in memory with the rest of the machine working.
    batches = output / ".batches"
    batches.mkdir(exist_ok=True)
    batch: dict[str, list[dict]] = collections.defaultdict(list)
    parts: dict[str, list[Path]] = collections.defaultdict(list)

    def empty() -> None:
        for name, rows in batch.items():
            if rows:
                parts[name].append(batches / f"{name}.{len(parts[name])}.csv")
                write(parts[name][-1], rows)
        batch.clear()

    players: list[dict] = []
    bad_ones, warnings, counts = [], [], 0
    with ProcessPoolExecutor(processes) as pool:
        for i, r in enumerate(pool.map(task, pairs), 1):
            if "error" in r:
                bad_ones.append(r)
                print(f"  ERROR  {r['game']}: {r['error']}", flush=True)
                continue
            if r["notice"]:
                warnings.append(r["game"])
                print(f"  WARNING  {r['game']}: {r['notice']}", flush=True)
            if leagues is not None:
                for f in r["players"] + [x for v in r["situations"].values() for x in v]:
                    f["league"] = leagues.get(f["game"], "")
            players += r["players"]
            for name, items in r["situations"].items():
                batch[name] += items
                counts += len(items)
            if i % 250 == 0:
                empty()
            if i % 25 == 0 or i == len(pairs):
                print(f"  {i}/{len(pairs)} · {len(players):,d} player rows · {counts:,d} situations", flush=True)
    empty()
    if leagues is not None:
        unmatched = {f["game"] for f in players if not f["league"]}
        print(f"league for {len(pairs) - len(bad_ones) - len(unmatched)} games" + (f", {len(unmatched)} without it" if unmatched else ""))

    write(output / "players.csv", players)
    print(f"\nplayers.csv · {len(players):,d} rows × {len(players[0]) if players else 0} columns")
    for name in CONCEPTS:
        if parts[name]:
            rows, columns = merge_files(output / f"{name}.csv", parts[name])
            print(f"{name}.csv · {rows:,d} rows × {columns} columns")
    shutil.rmtree(batches)
    if bad_ones:
        print(f"\n{len(bad_ones)} games were left out: " + ", ".join(r["game"] for r in bad_ones[:8]))
    if warnings:
        print(f"\n{len(warnings)} games without value: " + ", ".join(warnings[:8]))
    assert players, "no game gave any rows: is it the harvest folder?"
    # a match is ten players, not one more or less
    assert len(players) == 10 * (len(pairs) - len(bad_ones)), f"{len(players)} rows for {len(pairs)} games"


if __name__ == "__main__":
    main()
