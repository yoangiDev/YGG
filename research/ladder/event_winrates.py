"""Winrate of each match event and what it really adds.

    python research/ladder/event_winrates.py research/ladder/data

For each turret, dragon, Baron... of the team that takes it: how many times it happens, with
what winrate, the WP it already had just before (the app's model, wpa_model.py), its WPA
with consequences (winrate - prior WP, the report's definition) and the immediate
change in WP the model gives. The winrate is only association: an inhibitor is
taken by whoever is already winning. It leaves data/event_winrates.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from ygg_core.metrics.wpa import GameState, team_win_probability
from ygg_core.metrics.wpa_model import MODEL

sys.path.insert(0, str(Path(__file__).parent))
from analyse import load, wpa_summary
from export_wpa_model import as_riot

EVENTS = {
    "FIRST_BLOOD": "First blood",
    "FIRST_TOWER": "First turret of the game",
    "TOWER_OUTER_TOP": "T1 top",
    "TOWER_OUTER_MID": "T1 mid",
    "TOWER_OUTER_BOT": "T1 bot",
    "TOWER_INNER_TOP": "T2 top",
    "TOWER_INNER_MID": "T2 mid",
    "TOWER_INNER_BOT": "T2 bot",
    "TOWER_BASE": "T3 (inhibitor turret)",
    "INHIBITOR": "Inhibitor",
    "TOWER_NEXUS": "Nexus turret",
    "FIRST_DRAGON": "First dragon of the game",
    "DRAGON_1": "Team's 1st dragon",
    "DRAGON_2": "Team's 2nd dragon",
    "DRAGON_3": "Team's 3rd dragon (soul point)",
    "DRAGON_4": "Soul",
    "ELDER": "Elder dragon",
    "HORDE": "Void grub (each)",
    "RIFTHERALD": "Herald",
    "BARON_NASHOR": "Baron",
}


def _events(state: GameState) -> list[tuple[str, int, int]]:
    """(event, team that takes it, instant) of a match."""
    out = []
    first_blood = next((k for k in state.kills if k.get("killerId") in state.team_of), None)
    if first_blood:
        out.append(("FIRST_BLOOD", state.team_of[first_blood["killerId"]], int(first_blood["timestamp"])))
    taken = [o for o in state.objectives if o.team in (100, 200)]
    for kind, starts in (("FIRST_TOWER", "TOWER"), ("FIRST_DRAGON", "DRAGON_")):
        first = next((o for o in taken if o.kind.startswith(starts)), None)
        if first:
            out.append((kind, first.team, first.time))
    return out + [(o.kind, o.team, o.time) for o in taken if o.kind in EVENTS]


def main() -> None:
    data = Path(sys.argv[1])
    _players, records = load(data)
    pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)  # event: (won, prior WP)
    immediate: dict[str, list[float]] = defaultdict(list)  # event: WP after - before

    for record in records.values():
        match_data, timeline = as_riot(record)
        state = GameState(match_data, timeline)
        winner = next(t["teamId"] for t in match_data["info"]["teams"] if t["win"])
        for kind, team, t in _events(state):
            before = team_win_probability(state, team, t - 1, MODEL)
            pairs[kind].append((float(team == winner), before))
            immediate[kind].append(team_win_probability(state, team, t + 1, MODEL) - before)

    rows = []
    for kind, label in EVENTS.items():
        if not pairs[kind]:
            continue
        summary = wpa_summary(pairs[kind])
        summary["immediate"] = round(100 * float(np.mean(immediate[kind])), 2)
        rows.append({"event": kind, "name": label, **summary})

    print(f"{len(records)} games with timeline\n")
    print("| Event | Times | Winrate | WP just before | WPA (winrate - WP before) | Immediate change |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['name']} | {r['n']} | {r['winrate']} % | {r['wp_previous']} % | "
              f"{r['wpa']:+.1f} ± {r['error']:.1f} | {r['immediate']:+.1f} |")
    (data / "event_winrates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
