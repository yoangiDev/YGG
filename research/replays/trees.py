"""Decision trees for the sparse decisions: options, outcomes with their probability and their value in WP.

    python research/replays/trees.py <situations.json> <champion> <team> --rows <game.csv.gz>
                                       --fights <fights.csv> --setups <setups.csv>

`situations.json` is what `features.one_game` returns for that match; `--rows`, its rows from `policy.py
filas`; `--fights` and `--setups`, the ladder tables left by `features.py --value` (with their `value` column).

For a match (the situations `features.one_game` produces) and a player:

- **each fight they enter**: with how many on each side and how much gold in items, the ladder is searched for
  fights in the same state (same number on each side and the same bracket of gold difference) and it is counted how they
  ended —the one with more deaths wins, a draw if the same— and how much each outcome moved their team's WP
  (`value` from `value.py`, in neutral WP points). The expected value of entering is the sum of probability times
  value; the alternative, not fighting, is taken as 0: nothing changes. Catches (them alone against two or more) are not a
  decision to fight but about where they were before, and come out separately;
- **each objective the enemy takes**: with the living and the team's gold at that moment, the ladder's objectives in the same state
  are compared, those in which the team **showed up** (20 s or more in the zone) with those in which it **did not** (5 s or less):
  how many were taken from them and how much the WP moved over the objective's window.

What this doesn't know: whether there really was a choice (sometimes the fight finds you), the wave, the vision and the
cooldowns. The probabilities are associations in similar states, not experiments: whoever enters a fight at a
disadvantage may have a reason that isn't seen here. That is why each value carries its interval (90%, resampling
whole matches) and is read as what usually happens in that state, not as what would have happened in this match.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

GOLD_CUTS = [-1e9, -3000, -1500, -500, 500, 1500, 3000, 1e9]  # item gold difference of those fighting
MINIMUM = 100  # similar fights with which an estimate is accepted
PRESENT, ABSENT = 20, 5  # seconds in the objective's zone to count as showing up or not


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _ci(s: pd.DataFrame, n: int = 400) -> tuple[float, float]:
    """90% interval of the mean value, resampling whole matches (the situations of a match are not
    independent)."""
    g = s.groupby("game")["value"].agg(["sum", "count"])
    rng, idx = np.random.default_rng(0), np.arange(len(g))
    means = []
    for _ in range(n):
        k = rng.choice(idx, len(idx))
        means.append(g["sum"].to_numpy()[k].sum() / g["count"].to_numpy()[k].sum())
    return float(np.percentile(means, 5)), float(np.percentile(means, 95))


def fights_by_team(path: Path) -> pd.DataFrame:
    """The ladder's fights seen from each of the two teams."""
    c = pd.read_csv(path, usecols=["champions_100", "champions_200", "gold_100", "gold_200", "deaths_100",
                                   "deaths_200", "value_100", "game"])
    sides = []
    for me, other, sign in (("100", "200", 1), ("200", "100", -1)):
        sides.append(pd.DataFrame({"n_mine": c[f"champions_{me}"], "n_own": c[f"champions_{other}"],
                                   "gold": c[f"gold_{me}"] - c[f"gold_{other}"],
                                   "res": np.sign(c[f"deaths_{other}"] - c[f"deaths_{me}"]),
                                   "value": sign * c["value_100"], "game": c["game"]}))
    d = pd.concat(sides, ignore_index=True)
    d = d[d["value"].notna()]
    d["stretch"] = pd.cut(d["gold"], GOLD_CUTS, labels=False)
    return d


def fight_tree(d: pd.DataFrame, n_mine: int, n_own: int, gold: float) -> dict | None:
    """Wins / draws / loses, with their probability and value, in the ladder's fights in the same state."""
    stretch = int(pd.cut([gold], GOLD_CUTS, labels=False)[0])
    s = d[(d["n_mine"] == min(n_mine, 5)) & (d["n_own"] == min(n_own, 5)) & (d["stretch"] == stretch)]
    if len(s) < MINIMUM:
        return None
    branches = {}
    for res, name in ((1, "wins"), (0, "ties"), (-1, "loses")):
        t = s[s["res"] == res]
        branches[name] = {"p": len(t) / len(s), "value": float(t["value"].mean()) if len(t) else 0.0}
    return {"cases": len(s), "games": int(s["game"].nunique()), "branches": branches,
            "expected": float(s["value"].mean()), "ci": _ci(s)}


def objective_tree(setups: pd.DataFrame, objective: str, alive: int, gold_k: float) -> dict | None:
    """Showing up or not to an objective, in the ladder's objectives with the same living and similar gold."""
    name = "Dragon" if objective.startswith("Dragon") else objective.split(" ")[0]
    base = setups[setups["objective"].str.startswith(name) & (setups["alive"] == alive)
                  & setups["gold_team"].between(gold_k - 2.25, gold_k + 2.25)]
    out = {}
    for key, sel in (("shows up", base["presence"] >= PRESENT), ("does not show up", base["presence"] <= ABSENT)):
        s = base[sel]
        if len(s) < 30:
            return None
        out[key] = {"cases": len(s), "takes_it": float(s["takes_it"].mean()),
                        "expected": float(s["value"].mean()), "ci": _ci(s)}
    return out


def report(situations: dict, champion: str, team: str, fights: pd.DataFrame, setups: pd.DataFrame,
            rows: pd.DataFrame, deaths: list[float]) -> str:
    """The trees of the player's fights and of the objectives their team lost, in markdown. `rows` are
    theirs from `policy.py rows` (the state every 10 s): from there come the living and their team's gold before each
    objective, measured as in `value.annotate` (extra living and total gold in thousands)."""
    side, other = ("100", "200") if team == "100" else ("200", "100")
    lines = [f"## Fights of {champion}\n",
              "Value in neutral WP points for their team; not fighting = 0. In brackets, the 90% interval.\n",
              "| minute | state | wins | ties | loses | expected value of entering | what happened |",
              "|---|---|---|---|---|---|---|"]
    caught = []
    for p in situations["situations"]["fights"]:
        who = str(p.get("who") or "").split("|")
        if champion not in who:
            continue
        n_mine, n_own = int(p[f"champions_{side}"]), int(p[f"champions_{other}"])
        my, own_items = int(p[f"deaths_{side}"]), int(p[f"deaths_{other}"])
        if my + own_items == 0 and not int(p["teamfight"]):
            continue  # an exchange with no deaths: it decides nothing
        gold = float(p[f"gold_{side}"]) - float(p[f"gold_{other}"])
        died = any(float(p["since"]) <= m <= float(p["until"]) + 3 for m in deaths)
        step = f"{own_items}-{my}" + (" (he dies)" if died else "")
        if n_mine == 1 and n_own >= 2:
            caught.append(f"- {_clock(float(p['since']))}: alone against {n_own}, {gold:+,.0f} gold. {step}.")
            continue
        a = fight_tree(fights, n_mine, n_own, gold)
        if a is None:
            continue
        r = a["branches"]
        lines.append(f"| {_clock(float(p['since']))} | {n_mine}v{n_own}, {gold:+,.0f} gold | {r['wins']['p']:.0%} "
                      f"({r['wins']['value']:+.1f}) | {r['ties']['p']:.0%} ({r['ties']['value']:+.1f}) | "
                      f"{r['loses']['p']:.0%} ({r['loses']['value']:+.1f}) | **{a['expected']:+.1f}** "
                      f"[{a['ci'][0]:+.1f}, {a['ci'][1]:+.1f}] · {a['cases']:,d} fights | {step} |")
    if caught:
        lines += ["\nCaught out (it was not a decision to fight, but of where they were):\n", *caught]
    lines += ["\n## Objectives the rival took\n",
               "State of their team a minute before it falls. Value of the objective's window for their team.\n",
               "| objective | minute | state of their team | shows up | does not show up | their team |",
               "|---|---|---|---|---|---|"]
    own_rows = rows[rows["champion"] == champion].sort_values("t")
    # only those the enemy took: an objective that doesn't fall (the herald that leaves by itself) was lost by nobody
    of_the_rival = {(s["objective"], float(s["time"])) for s in situations["situations"]["setups"]
                 if str(s["team"]) == other and int(s["takes_it"])}
    for s in situations["situations"]["setups"]:
        if str(s["team"]) != team or (s["objective"], float(s["time"])) not in of_the_rival:
            continue
        falls_ = float(s["time"])
        before = own_rows[own_rows["t"] <= falls_ - 60]
        if before.empty:
            continue
        f = before.iloc[-1]
        alive, gold = int(f["allies_alive"]) + 1 - int(f["rivals_alive"]), float(f["gold_team"])
        a = objective_tree(setups, s["objective"], alive, gold)
        did = f"showed up ({int(s['presence'])} s)" if int(s["presence"]) >= PRESENT else (
            f"did not show up ({int(s['presence'])} s)" if int(s["presence"]) <= ABSENT else
            f"half way ({int(s['presence'])} s)")
        if a is None:
            lines.append(f"| {s['objective']} | {_clock(falls_)} | alive {alive:+d}, gold {gold:+.1f}k | few cases | | {did} |")
            continue
        yes_, no_ = a["shows up"], a["does not show up"]
        lines.append(f"| {s['objective']} | {_clock(falls_)} | alive {alive:+d}, gold {gold:+.1f}k | taken "
                      f"{yes_['takes_it']:.0%} of the time, **{yes_['expected']:+.1f}** [{yes_['ci'][0]:+.1f}, {yes_['ci'][1]:+.1f}] · "
                      f"{yes_['cases']} | taken {no_['takes_it']:.0%} of the time, **{no_['expected']:+.1f}** "
                      f"[{no_['ci'][0]:+.1f}, {no_['ci'][1]:+.1f}] · {no_['cases']} | {did} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("situations", type=Path)
    ap.add_argument("champion")
    ap.add_argument("team", choices=["100", "200"])
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--fights", type=Path, required=True)
    ap.add_argument("--setups", type=Path, required=True)
    ap.add_argument("--deaths", default="", help="the seconds at which they die, comma-separated")
    a = ap.parse_args()
    situations = json.loads(a.situations.read_text(encoding="utf-8"))
    print(report(situations, a.champion, a.team, fights_by_team(a.fights), pd.read_csv(a.setups),
                  pd.read_csv(a.rows), [float(m) for m in a.deaths.split(",") if m]))


if __name__ == "__main__":
    main()
