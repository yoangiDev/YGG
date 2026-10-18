"""Economy: gold and XP against the ideal (Challenger), by role and minute.

    python research/ladder/economy.py research/ladder/data

The expected reference is the IDEAL, not the player's league: the mean of the Challenger
players in the study (research/ladder/data, roster.json → their matches in their role),
like the app's grade, which always compares against Challenger. A player has a good
economy if their gold and XP per minute come close to those of a Challenger in their role.

With the second argument (data/tiers) it also measures how far each league is from the
ideal: the mean gold and XP lag against Challenger at each minute.

It leaves data/economy_reference.json: per (role, minute) Challenger's mean gold and XP
and their deviation. Basis of the economy metric (docs/model/player_performance.md §4.1);
valuing it in win points and the cost of dying come later.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from ygg_core.metrics.wpa import PHASES
from ygg_core.metrics.wpa_model import MODEL

sys.path.insert(0, str(Path(__file__).parent))
from analyse import auc, load

ROLES = ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")
TIERS = ("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER")
GOLD, XP = 1, 2  # indices in frame_fields
MAX_MINUTE = 35
START_MINUTE = 5  # before that there is almost no difference and the noise of the first minutes dominates


def economy_points(frames: list, role: str, ideal: dict) -> float | None:
    """Win points (neutral) contributed by the player's economy: their gold and XP against the ideal.

    At each minute, the gold and XP lag is valued with the model's gold/xp weight in that stretch
    (log-odds per 1000), and converted to points as in the grade (at 50%, 25 points per log-odd).
    It is averaged over the minutes: 'on average, your economy put your team ±X points against a
    Challenger of your role'. It includes gold from kills and objectives (separating farming gold is pending).
    """
    points = []
    for f in frames:
        minute = f[0]
        if minute < START_MINUTE or (role, minute) not in ideal:
            continue
        phase = MODEL.coefficients[max(i for i, p in enumerate(PHASES) if minute >= p)]
        gm, _gs, xm, _xs, _n = ideal[(role, minute)]
        logit = phase[1] * (f[GOLD] - gm) / 1000 + phase[2] * (f[XP] - xm) / 1000
        points.append(25 * logit)
    return float(np.mean(points)) if points else None


def challenger_curves(data: Path) -> dict[tuple[str, int], tuple[float, float, float, float, int]]:
    """(role, minute) → (mean gold, gold sd, mean xp, xp sd, n) of the roster's Challengers in their role."""
    players, records = load(data)
    gold: dict = defaultdict(lambda: defaultdict(list))
    xp: dict = defaultdict(lambda: defaultdict(list))
    for entry in players.values():
        role, puuid = entry["role"], entry["puuid"]
        for match_id in entry.get("games") or []:
            record = records.get(match_id)
            if not record or record.get("remake"):
                continue
            pid = next((p["participantId"] for p in record["participants"] if p["puuid"] == puuid), None)
            frames = record["frames"].get(str(pid)) if pid else None
            duration = record.get("duration", 0) / 60
            if not frames:
                continue
            for f in frames:
                if f[0] <= MAX_MINUTE and duration > f[0]:
                    gold[role][f[0]].append(f[GOLD])
                    xp[role][f[0]].append(f[XP])
    out = {}
    for role in ROLES:
        for minute in range(MAX_MINUTE + 1):
            g, x = np.array(gold[role][minute]), np.array(xp[role][minute])
            if len(g) >= 30:
                out[(role, minute)] = (float(g.mean()), float(g.std()), float(x.mean()), float(x.std()), len(g))
    return out


def tier_gap(tiers_data: Path, ideal: dict) -> dict[str, dict[str, float]]:
    """Mean gold and XP lag of each league against the Challenger ideal, averaging minutes 10-25 and roles."""
    lag: dict = defaultdict(lambda: {"gold": [], "xp": []})
    with gzip.open(tiers_data / "matches.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            if record.get("missing") or record.get("remake") or not record.get("frames"):
                continue
            tier = record.get("tier")
            if tier not in TIERS:
                continue
            duration = record.get("duration", 0) / 60
            for p in record["participants"]:
                role, frames = p.get("role"), record["frames"].get(str(p["participantId"]))
                if role not in ROLES or not frames:
                    continue
                for f in frames:
                    if 10 <= f[0] <= 25 and (role, f[0]) in ideal and duration > f[0]:
                        gm, _gs, xm, _xs, _n = ideal[(role, f[0])]
                        lag[tier]["gold"].append(f[GOLD] - gm)
                        lag[tier]["xp"].append(f[XP] - xm)
    return {t: {"gold": round(float(np.mean(v["gold"])), 0), "xp": round(float(np.mean(v["xp"])), 0)} for t, v in lag.items()}


def main() -> None:
    ideal = challenger_curves(Path(sys.argv[1]))
    reference = {f"{role}|{minute}": {"gold_mean": round(g, 1), "gold_sd": round(gs, 1),
                                      "xp_mean": round(x, 1), "xp_sd": round(xs, 1), "n": n}
                 for (role, minute), (g, gs, x, xs, n) in ideal.items()}
    (Path(sys.argv[1]) / "economy_reference.json").write_text(json.dumps({"reference": reference}, indent=1), encoding="utf-8")

    print("Challenger ideal — mean gold / XP per role:")
    print(f"  {'min':<5}" + "".join(f"{r:>16}" for r in ROLES))
    for minute in (10, 15, 20, 25):
        cells = []
        for role in ROLES:
            v = ideal.get((role, minute))
            cells.append(f"{v[0]:.0f}/{v[2]:.0f}" if v else "—")
        print(f"  {minute:<5}" + "".join(f"{c:>16}" for c in cells))

    if len(sys.argv) > 2:
        gaps = tier_gap(Path(sys.argv[2]), ideal)
        print("\nMean delay against the Challenger ideal (min 10-25, all roles):")
        for tier in TIERS:
            if tier in gaps:
                print(f"  {tier:<11} gold {gaps[tier]['gold']:+.0f}   xp {gaps[tier]['xp']:+.0f}")

        # Economy index in win points: by league, and whether it separates wins within the league.
        points: dict = defaultdict(lambda: {"pts": [], "won": []})
        with gzip.open(Path(sys.argv[2]) / "matches.jsonl.gz", "rt", encoding="utf-8") as fh:
            for line in fh:
                record = json.loads(line)
                if record.get("missing") or record.get("remake") or not record.get("frames"):
                    continue
                tier = record.get("tier")
                if tier not in TIERS:
                    continue
                for p in record["participants"]:
                    role, frames = p.get("role"), record["frames"].get(str(p["participantId"]))
                    if role not in ROLES or not frames:
                        continue
                    value = economy_points(frames, role, ideal)
                    if value is not None:
                        points[tier]["pts"].append(value)
                        points[tier]["won"].append(float(p.get("win", False)))
        print("\nEconomy index (win points vs the Challenger ideal), per league:")
        for tier in TIERS:
            pts = np.array(points[tier]["pts"])
            won = np.array(points[tier]["won"])
            print(f"  {tier:<11} mean {pts.mean():+5.2f}   winning {pts[won == 1].mean():+5.2f} / "
                  f"losing {pts[won == 0].mean():+5.2f}   AUC vs win {auc(pts, won):.3f}")


if __name__ == "__main__":
    main()
