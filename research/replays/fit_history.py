"""Fits the history grade to the analysis grade, using only what Riot's API gives (match and timeline).

The analysis grade comes from the replay (`coach.grade`: what its moments add and subtract, in WP points at 30 minutes). The history one only
has the match and its timeline. This takes, from each player in a sample, the variables the API gives, joins them with their analysis grade
(`grade_history.py`) and fits a regression per position. It compares with today's stats grade (`ygg_core.metrics.match_score`).

    python research/replays/fit_history.py <grades-per-player.jsonl> <matches.jsonl.gz> [--output model.json]
"""

from __future__ import annotations

import collections
import gzip
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from ygg_core.metrics import match_score as MS
from ygg_core.metrics.timeline_grade import variables

POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
ROLE = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}


def stats_score(r: dict, p: dict) -> float:
    """Today's stats grade (match_score.weighted_score) with the match data, unclamped."""
    d = max(r["duration"] / 60, 1.0)
    team = p["teamId"]
    kills_total = sum(q["kills"] for q in r["participants"])
    gold = sum(q["goldEarned"] for q in r["participants"] if q["teamId"] == team)
    c = p.get("challenges") or {}
    part = SimpleNamespace(
        role=ROLE.get(p.get("teamPosition") or "", "MID"), kills=p["kills"], deaths=p["deaths"], assists=p["assists"],
        cs_per_min=(p["totalMinionsKilled"] + p["neutralMinionsKilled"]) / d, damage_per_min=p["totalDamageDealtToChampions"] / d,
        damage_share=100 * c.get("teamDamagePercentage", 0.0), kill_participation=100 * c.get("killParticipation", 0.0))
    return MS.weighted_score(part, pace=MS.pace_factor(kills_total), gold_share=100 * p["goldEarned"] / max(1, gold))


def load(grades: Path, games: Path):
    per_game = {}
    for line in grades.read_text(encoding="utf-8").splitlines():
        n = json.loads(line)
        per_game[n["game"]] = n
    which_ones = set(per_game)
    rows = []
    with gzip.open(games, "rt", encoding="utf-8") as fh:
        for line in fh:
            m = re.search(r'"match_id":\s*"([^"]+)"', line[:80])
            mid = m.group(1).replace("_", "-")
            if mid not in which_ones:
                continue
            r = json.loads(line)
            if r.get("remake"):
                continue
            n = per_game[mid]
            by_champion = {(str(j["team"]), j["champion"].lower()): j for j in n["players"]}
            for p in r["participants"]:
                j = by_champion.get((str(p["teamId"]), p["championName"].lower()))
                if j is None or not p.get("teamPosition"):
                    continue
                v = variables(r, p)
                rows.append({"game": mid, "league": n["league"], "position": p["teamPosition"], "total": j["total"], "stats": stats_score(r, p), "x": v})
    return rows


def ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, float]:
    A = X.T @ X + alpha * np.eye(X.shape[1])
    w = np.linalg.solve(A, X.T @ y)
    return w, float(y.mean() - 0)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def grade(total: np.ndarray | float, cuts: list[float]):
    """The same conversion as `coach.grades`: the analysis points brought to 1-100 with the position's Challenger percentiles."""
    f = lambda t: max(1, min(100, round(MS.metric_score("wpa", float(t), tuple(cuts)))))  # noqa: E731
    return np.array([f(t) for t in total]) if isinstance(total, np.ndarray) else f(total)


def main() -> None:
    rows = load(Path(sys.argv[1]), Path(sys.argv[2]))
    output = Path(sys.argv[sys.argv.index("--output") + 1]) if "--output" in sys.argv else None
    challenger_cuts = json.loads((Path(sys.argv[2]).parent / "grades.json").read_text(encoding="utf-8"))["CHALLENGER"]
    print(f"{len(rows)} players from {len({f['game'] for f in rows})} games", flush=True)
    names = sorted(rows[0]["x"])
    model: dict = {"variables": names, "positions": {}}
    print(f"{len(names)} variables")
    print()
    for position in POSITIONS:
        fs = [f for f in rows if f["position"] == position]
        if len(fs) < 40:
            continue
        X = np.array([[f["x"][n] for n in names] for f in fs], dtype=float)
        y = np.array([f["total"] for f in fs], dtype=float)
        s_ = np.array([f["stats"] for f in fs], dtype=float)
        mu, sd = X.mean(0), X.std(0) + 1e-9
        Z = (X - mu) / sd
        groups = sorted({f["game"] for f in fs})
        fold = {g: i % 5 for i, g in enumerate(groups)}
        pred = np.zeros(len(fs))
        for k in range(5):
            tr = np.array([fold[f["game"]] != k for f in fs])
            ym = y[tr].mean()
            w, _ = ridge(Z[tr], y[tr] - ym, alpha=30.0)
            pred[~tr] = Z[~tr] @ w + ym
        cuts = challenger_cuts[position]
        truth = grade(y, cuts)
        today = np.array([MS.final_score(v) for v in s_]).round().clip(1, 100)
        new_ = grade(pred, cuts)
        print(f"{position:8} Spearman with the analysis grade: today {spearman(s_, y):+.2f} → model {spearman(pred, y):+.2f} | "
              f"mean error in grade points: today {np.abs(today - truth).mean():.1f} → model {np.abs(new_ - truth).mean():.1f} | "
              f"bias: today {np.mean(today - truth):+.1f}, model {np.mean(new_ - truth):+.1f} | "
              f"within ±10 points: today {np.mean(np.abs(today - truth) <= 10):.0%} → model {np.mean(np.abs(new_ - truth) <= 10):.0%}", flush=True)
        w, _ = ridge(Z, y - y.mean(), alpha=30.0)
        model["positions"][position] = {"mean": float(y.mean()), "mu": mu.round(4).tolist(), "sd": sd.round(4).tolist(), "weight": w.round(4).tolist(),
                                     "cuts": cuts}
        biggest = sorted(zip(names, w), key=lambda t: -abs(t[1]))[:7]
        print("         biggest weights:", ", ".join(f"{n} {v:+.2f}" for n, v in biggest), flush=True)
    if output:
        output.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"model saved in {output}")


if __name__ == "__main__":
    main()
