"""Fits the app's WP model and generates ygg_core/metrics/wpa_model.py.

    python research/ladder/export_wpa_model.py research/ladder/data

It uses the same code as the app (ygg_core.metrics.wpa) over the study's matches:

0. Gold of each event type: regression of the gold jump between frames against the
   events of that minute. The state adds it instantly, without waiting for the frame.
   Kill and shutdown go separately: shutdown barely gives assist gold.
1. State features every 30 s, seen from both teams → one logistic regression per
   stretch of the game. Without the study's draft feature: the app doesn't have
   each champion's winrate.
2. Calibration validated per match (5 folds).
3. With that model, the total (neutral) WPA of each match of the 50 roster
   players in their role → mean and deviation per role: the grade's reference (70 = their mean).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from ygg_core.metrics.wpa import FEATURES, GOLD_EVENTS, PHASES, GameState, WinModel, wpa_report

sys.path.insert(0, str(Path(__file__).parent))
from analyse import auc, folds, load, logistic_fit, logistic_predict

OUT = Path(__file__).resolve().parents[2] / "packages/ygg-core/src/ygg_core/metrics/wpa_model.py"
SAMPLE_EVERY_MS = 30_000


def as_riot(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compact record of ladder_dataset.py → the shape of the Riot payloads the app reads."""
    match_data = {"info": {"participants": record["participants"], "teams": record["teams"], "gameDuration": record["duration"]}}
    frames_by_pid = record["frames"]
    count = min(len(rows) for rows in frames_by_pid.values())
    frames = [
        {
            "timestamp": m * 60_000,
            "participantFrames": {pid: {"totalGold": rows[m][1], "xp": rows[m][2], "level": rows[m][3]} for pid, rows in frames_by_pid.items()},
            "events": [],
        }
        for m in range(count)
    ]
    frames[0]["events"] = record["events"]  # GameState sorts them by time
    return match_data, {"info": {"frames": frames}}


def mirror(x: list[float]) -> list[float]:
    return [-v for v in x[:-1]] + [x[-1]]


def phase_of(minute: float) -> int:
    return max(i for i, start in enumerate(PHASES) if minute >= start)


def event_gold(states: dict[str, GameState]) -> dict[str, float]:
    design, jumps = [], []
    for state in states.values():
        for counts, jump in state.gold_intervals():
            design.append([counts.get(kind, 0.0) for kind in GOLD_EVENTS])
            jumps.append(jump)
    solution, *_ = np.linalg.lstsq(np.array(design), np.array(jumps), rcond=None)
    return {kind: round(float(v), 3) for kind, v in zip(GOLD_EVENTS, solution, strict=True)}


# Advantages that can't subtract: without this, with gold fixed, "having taken a turret" before 15 came out
# with a negative weight (it is associated with having traded it for something elsewhere), and losing a turret raised the WP.
NON_NEGATIVE = [i for i, name in enumerate(FEATURES) if name not in ("minute",)]


def fit_non_negative(x: np.ndarray, y: np.ndarray, non_negative: list[int] = NON_NEGATIVE) -> np.ndarray:
    """Logistic regression in which the advantages (the columns of `non_negative`) can't weigh against: the most
    negative is dropped and refitted."""
    active = list(range(x.shape[1]))
    while True:
        w = logistic_fit(x[:, active], y)
        weights = dict(zip(active, w[1:], strict=True))
        negative = [j for j in active if j in non_negative and weights[j] < 0]
        if not negative:
            break
        active.remove(min(negative, key=lambda j: weights[j]))
    full = np.zeros(x.shape[1] + 1)
    full[0] = w[0]
    for j, value in weights.items():
        full[j + 1] = value
    return full


def fit(states: dict[str, GameState], riot: dict[str, Any], gold: dict[str, float]) -> tuple[tuple[float, ...], ...]:
    rows, labels, keys = [], [], []
    for match_id, state in states.items():
        blue_won = 1.0 if next(t["teamId"] for t in riot[match_id][0]["info"]["teams"] if t["win"]) == 100 else 0.0
        for t in range(60_000, state.duration_ms, SAMPLE_EVERY_MS):
            x = state.features(t, gold)
            rows += [x, mirror(x)]
            labels += [blue_won, 1 - blue_won]
            keys += [match_id, match_id]
    x, y = np.array(rows), np.array(labels)
    phase = np.array([phase_of(m) for m in x[:, -1]])
    fold = folds(keys)
    held_out = np.zeros(len(y))
    for k in range(5):
        for p in range(len(PHASES)):
            train, test = (fold != k) & (phase == p), (fold == k) & (phase == p)
            if test.any():
                held_out[test] = logistic_predict(fit_non_negative(x[train], y[train]), x[test])
    bins = np.minimum((held_out * 10).astype(int), 9)
    ece = sum(abs(held_out[bins == b].mean() - y[bins == b].mean()) * (bins == b).sum() for b in range(10) if (bins == b).any()) / len(y)
    print(f"model: AUC {auc(held_out, y):.3f} · calibration ±{100 * ece:.2f} pp")
    for b in range(10):
        if (bins == b).any():
            print(f"  predicts {100 * held_out[bins == b].mean():5.1f} → won {100 * y[bins == b].mean():5.1f}")
    return tuple(tuple(round(float(v), 6) for v in fit_non_negative(x[phase == p], y[phase == p])) for p in range(len(PHASES)))


def reference(players: dict[str, Any], riot: dict[str, Any], model: WinModel) -> dict[str, tuple[float, float]]:
    """Total WPA of each roster match in their role, with the app's split → mean and deviation per role."""
    totals: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for entry in players.values():
        for match_id in entry.get("games") or []:
            if match_id not in riot:
                continue
            match_data, timeline = riot[match_id]
            report = wpa_report(match_data, timeline, entry["puuid"], model)
            if report is None:
                continue
            me = next(p for p in match_data["info"]["participants"] if p["puuid"] == entry["puuid"])
            won = next(t["win"] for t in match_data["info"]["teams"] if t["teamId"] == me["teamId"])
            totals[entry["role"]].append((report.total, won))
    return {role: (round(float(np.mean([v for v, _ in vals])), 3), round(float(np.std([v for v, _ in vals])), 3)) for role, vals in totals.items()}


def report_grades(players: dict[str, Any], riot: dict[str, Any], model: WinModel) -> None:
    """With the reference already set: how the roster's own grades are distributed."""
    rows: dict[str, list[tuple[int, bool, bool]]] = defaultdict(list)
    for entry in players.values():
        for match_id in entry.get("games") or []:
            if match_id not in riot:
                continue
            match_data, timeline = riot[match_id]
            report = wpa_report(match_data, timeline, entry["puuid"], model)
            if report is None or report.grade is None:
                continue
            me = next(p for p in match_data["info"]["participants"] if p["puuid"] == entry["puuid"])
            won = next(t["win"] for t in match_data["info"]["teams"] if t["teamId"] == me["teamId"])
            bad = me["deaths"] >= 8 and me["kills"] + me["assists"] < me["deaths"]
            rows[entry["role"]].append((report.grade, won, bad))
    for role, vals in sorted(rows.items()):
        grades = np.array([g for g, _, _ in vals], dtype=float)
        won = np.array([w for _, w, _ in vals])
        bad = np.array([b for _, _, b in vals])
        print(f"  {role:<8} AUC {auc(grades, won.astype(float)):.3f} · mean grade {grades[won].mean():.0f} winning / "
              f"{grades[~won].mean():.0f} losing · defeats ≥ 70: {np.mean(grades[~won] >= 70):.1%} · "
              f"≥ 8 deaths and KDA < 1: {grades[bad].mean():.0f} (n={bad.sum()}) · p5 {np.percentile(grades, 5):.0f} · "
              f"min {grades.min():.0f}")


def write(model: WinModel) -> None:
    nl = "\n"
    rows = f",{nl}".join(f"        ({', '.join(repr(v) for v in row)})" for row in model.coefficients)
    golds = f",{nl}".join(f'        "{kind}": {value!r}' for kind, value in model.event_gold.items())
    refs = f",{nl}".join(f'        "{role}": {model.reference[role]!r}' for role in sorted(model.reference))
    OUT.write_text(
        f'"""WP model and grade reference. Generated by research/ladder/export_wpa_model.py: do not edit by hand."""{nl}{nl}'
        f"from ygg_core.metrics.wpa import WinModel{nl}{nl}"
        f"# Features: {', '.join(FEATURES)}. Stretches (minutes): {', '.join(map(str, PHASES))}.{nl}"
        f"MODEL = WinModel({nl}"
        f"    coefficients=({nl}{rows},{nl}    ),{nl}"
        f"    # Gold per event, measured with the gold jump between frames (KILL and SHUTDOWN: multipliers of their reward).{nl}"
        f"    event_gold={{{nl}{golds},{nl}    }},{nl}"
        f"    # Role: (mean, standard deviation) of the total WPA per match of the 50 Challengers in the study.{nl}"
        f"    reference={{{nl}{refs},{nl}    }},{nl}"
        f"){nl}",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


def main() -> None:
    data = Path(sys.argv[1])
    players, records = load(data)
    riot = {match_id: as_riot(r) for match_id, r in records.items()}
    states = {match_id: GameState(*pair) for match_id, pair in riot.items()}
    print(f"{len(riot)} games")

    gold = event_gold(states)
    print("gold per event:", gold)
    coefficients = fit(states, riot, gold)
    refs = reference(players, riot, WinModel(coefficients=coefficients, event_gold=gold, reference={}))
    model = WinModel(coefficients=coefficients, event_gold=gold, reference=refs)
    report_grades(players, riot, model)
    write(model)
    (data / "wpa_reference.json").write_text(json.dumps({"reference": refs, "event_gold": gold}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
