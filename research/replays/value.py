"""How much each situation is worth and whose it is: the per-second WP from `wp_per_second.py` applied to the features tables.

    python research/replays/value.py model <wp_per_second folder> <output folder>
    python research/replays/value.py noise <harvest> <matches.jsonl.gz> <output folder> [--processes 3]
    python research/replays/features.py <harvest> <features> --leagues <matches.jsonl.gz> --value <model.json>
    python research/replays/value.py effects <features folder>

The first refits the Phase 3 model without negative weights; the second measures the curve's background noise
to choose the windows; with both, `features.py --value` adds to the tables the value of each situation and
whose it is (`annotate`) and the decision tables (`roam_decisions`, `flash_decisions`); and `effects` compares
decisions in the same game state: roam or stay?, spend the flash or keep it? What comes out, and
why, in `value.md`.

1. **Model** (`model`): `wp_per_second.py`'s has negative weights on advantages (kills from 20, dragons
   from 30, mana…). It is collinearity, not that killing subtracts, but for splitting a WP change among
   what causes it —and among champions— it won't do: a kill would subtract on one side and add on another. It is refitted with
   `export_wpa_model.fit_non_negative` (the most negative advantage is dropped and it is refitted until none
   remain) and it is measured out of fold how much the prediction worsens. Only the `FREE` features remain free,
   which have a reason to weigh against.
2. **Curve** (`curve`): blue's log-odds at each second, and what each champion contributes (`contribution`). Since the
   model is linear and almost all its features are sums per champion (gold, XP, whether alive, how long until they
   return, their health…), the log-odds is the intercept, plus the timeline's (turrets, dragons…), plus the sum of
   each one's. That allows splitting a situation's value among those who play it without inventing weights.
3. **Noise** (`noise`): how much the difference between two windows moves when no particular
   moment is chosen. From there come `WINDOW` and what can and can't be said about a loose situation.
"""

from __future__ import annotations

import csv
import functools
import json
import math
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import moments as M
import numpy as np
import wp_per_second as W
from leagues import LEAGUES
from ygg_core.metrics.wpa import PHASES

# Features that may weigh against because they have a reason, not because of collinearity: with total gold inside, unspent
# gold is gold that isn't yet strength; with the health of those fighting inside, more bodies in range with the
# same health is more people hit; and being past the river is pressure, but also exposure.
FREE = ("unspent_k", "fight", "rival_side")
NON_NEGATIVE = [j for j, r in enumerate(W.ALL_FEATURES) if r not in FREE]
MODEL_FILE = Path(__file__).resolve().parents[1] / "ladder/data/harvest-16.19/value/model.json"
NEUTRAL = 100 / 4  # WP points per log-odds point at 50%, like the app's neutral WPA


# ── Model ─────────────────────────────────────────────────────────────────────


def _data(folder: Path):
    """`wp_per_second.evaluate`'s: the .npz states with their result, their stretch and their fold."""
    d = np.load(folder / "wp_per_second.npz")
    game, t = d["game"], d["t"]
    minute = t / 60
    return (d, game, t, d["x"].astype(float), d["wins"][game], minute,
            np.searchsorted(PHASES, minute, side="right") - 1, W.folds(d["ids"], d["leagues"])[game])


def model(folder: Path, output: Path) -> None:
    d, game, t, x, y, minute, phase, fold = _data(folder)
    print(f"# Model without negative weights · {len(d['ids'])} games · {len(y):,d} states\n")
    unconstrained = W.out_of_fold(x, y, phase, fold, minute, smooth=True)
    constrained = W.out_of_fold(x, y, phase, fold, minute, smooth=True, non_negative=NON_NEGATIVE)
    print("| model | log-loss | Brier | AUC | calibration (pp) | difference [90%] |\n|---|---|---|---|---|---|")
    loss = {k: np.logaddexp(0, z) - y * z for k, z in (("unconstrained", unconstrained), ("constrained", constrained))}
    for name, z in (("Phase 3 (full, smooth)", unconstrained), ("without negative weights", constrained)):
        m = W.metrics(z, y)
        a, b = W.interval(np.logaddexp(0, z) - y * z - loss["unconstrained"], game)
        print(f"| {name} | {m['log_loss']:.4f} | {m['brier']:.4f} | {m['auc']:.3f} | {m['ece']:.2f} | "
              f"[{a:+.4f}, {b:+.4f}] |")

    print("\n## How much it moves (consecutive state pairs, 10 s, no kills or objectives)\n")
    consecutive = (game[1:] == game[:-1]) & (np.diff(t) == W.STEP)
    kill = np.diff(x[:, W.ALL_FEATURES.index("kills")])
    quiet = consecutive & (kill == 0) & (np.abs(np.diff(x[:, 4:len(W.MACRO)], axis=0)).sum(axis=1) == 0)
    change = {k: 100 * np.diff(1 / (1 + np.exp(-z.clip(-30, 30)))) for k, z in (("unconstrained", unconstrained), ("constrained", constrained))}
    print("| model | mean change in quiet 10 s | in the 10 s of a kill |\n|---|---|---|")
    for k in change:
        print(f"| {k} | {np.abs(change[k][quiet]).mean():.2f} pp | "
              f"{np.mean(np.sign(kill[consecutive & (kill != 0)]) * change[k][consecutive & (kill != 0)]):+.2f} pp |")
    print(f"\nCorrelation between the 10 s changes of the two: "
          f"{np.corrcoef(change['unconstrained'][consecutive], change['constrained'][consecutive])[0, 1]:.3f}")

    weights = W.fit(x, y, phase, non_negative=NON_NEGATIVE)
    print("\n## Features that stay at 0, by stretch\n")
    for p, w in enumerate(weights):
        print(f"- {W.stretch(p)}: " + ", ".join(r for j, r in enumerate(W.ALL_FEATURES) if w[1 + j] == 0 and j in NON_NEGATIVE
                                               and x[phase == p, j].any()))
    print("\n## Weights without negative weights, standardized (log-odds per standard deviation of the feature in the stretch)\n")
    print("| feature | " + " | ".join(W.stretch(p) for p in range(len(PHASES))) + " |\n|---|" + "---|" * len(PHASES))
    dev = [x[phase == p].std(axis=0) for p in range(len(PHASES))]
    order = np.argsort(-np.mean([np.abs(w[1:] * s) for w, s in zip(weights, dev, strict=True)], axis=0))
    for j in order:
        print(f"| {W.ALL_FEATURES[j]} | " + " | ".join(f"{w[1 + j] * s[j]:+.2f}" for w, s in zip(weights, dev, strict=True)) + " |")

    base = json.loads((folder / "model.json").read_text(encoding="utf-8"))
    base |= {"non_negative": [[round(float(v), 6) for v in w] for w in weights], "free": FREE}
    output.mkdir(parents=True, exist_ok=True)
    (output / "model.json").write_text(json.dumps(base, indent=1), encoding="utf-8")
    print(f"\nwrote {output / 'model.json'}")


# ── Curve ──────────────────────────────────────────────────────────────────────


@functools.cache
def coefficients(path: Path = MODEL_FILE, which_ones: str = "non_negative") -> np.ndarray:
    """(stretch, intercept + one weight per feature) of the model: `non_negative` for splitting, `coefficients` the Phase 3
    one as it is."""
    return np.array(json.loads(Path(path).read_text(encoding="utf-8"))[which_ones])


def weights_at(minute: np.ndarray, coefs: np.ndarray) -> np.ndarray:
    """The weights for each second, blending the two neighbouring stretches like `wp_per_second.logits(smooth=True)`."""
    a = np.interp(minute, W.CENTRES, np.arange(len(W.CENTRES)))
    lo = np.floor(a).astype(int)
    hi = np.minimum(lo + 1, len(W.CENTRES) - 1)
    return (1 - (a - lo))[:, None] * coefs[lo] + (a - lo)[:, None] * coefs[hi]


def curve(record: dict, events: dict, state: Path, coefs: np.ndarray | None = None) -> dict:
    """The match's WP at each second (from `wp_per_second.FROM`):

    - `t`: the seconds, in order (an occasional one is missing if the table doesn't carry all ten);
    - `z`: blue's log-odds (red's is -z) and `wp`, its WP;
    - `contribution`: (second, champion) what each one puts into **their team's** log-odds, in the order of
      `events["players"]` (`champion`, `team`). z = intercept + timeline + Σ blue - Σ red;
    - `rest`: z minus the champions' part: the intercept, the timeline's (turrets, dragons, baron…) and the mana
      of a team in which nobody carries it;
    - `x` and `own_items`: blue's features and each champion's in favour of their team (`wp_per_second.states`)."""
    coefs = coefficients() if coefs is None else coefs
    e = W.states(record, events, W._seconds(Path(state), step=1), own_items=True)
    w = weights_at(e["t"] / 60, coefs)
    z = w[:, 0] + np.einsum("tk,tk->t", w[:, 1:], e["x"])
    contribution = np.einsum("tk,tck->tc", w[:, 1:], e["own_items"])
    sign = np.array([1.0 if p["team"] == "100" else -1.0 for p in events["players"]])
    return {"t": e["t"], "z": z, "wp": 1 / (1 + np.exp(-z.clip(-30, 30))), "contribution": contribution,
            "rest": z - contribution @ sign, "champion": [p["champion"] for p in events["players"]],
            "team": [p["team"] for p in events["players"]], "x": e["x"], "own_items": e["own_items"]}


# ── Background noise ──────────────────────────────────────────────────────────

WIDTHS = (1, 3, 5, 10, 15, 20, 30, 60)  # seconds of each window that are tried
SEPARATIONS = (0, 5, 15, 30, 60)  # seconds between the two windows: how long the situation lasts


def _means(t: np.ndarray, v: np.ndarray, since: np.ndarray, until: np.ndarray) -> np.ndarray:
    """The mean of `v` over the seconds of [since, until) of each pair, or nan if there are none."""
    running = np.r_[0.0, np.cumsum(v)]
    i, j = np.searchsorted(t, since), np.searchsorted(t, until)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(j > i, (running[j] - running[i]) / (j - i), np.nan)


def _one_for_noise(pair: tuple[dict, str, str]) -> dict:
    record, state, events_path = pair
    try:
        with M.open_file(Path(events_path)) as fh:
            events = M.drop_revived(json.load(fh))
        c = curve(record, events, Path(state))
    except Exception as e:  # a strange match can't stop five hundred
        return {"error": f"{type(e).__name__}: {e}"}
    team = {p["net_id"]: p["team"] for p in events["players"]}
    # when someone dies, and in whose favour (the team that doesn't die): the signal against which noise is measured
    deaths = [(e["time"], 1.0 if team[e["net_id"]] == "200" else -1.0) for e in events["events"]
               if e["type"] == "Death" and e["net_id"] in team]
    objectives = [e["timestamp"] / 1000 for e in record["events"]
                 if e["type"] in ("BUILDING_KILL", "ELITE_MONSTER_KILL")]
    return {"t": c["t"], "z": c["z"].astype(np.float32), "deaths": deaths, "objectives": objectives,
            "league": record["tier"]}


def noise(harvest: Path, games: Path, output: Path, processes: int, one_in: int = 10) -> None:
    """For each window width and each separation between windows, how much the mean of the later window changes
    relative to the earlier one at arbitrary instants (every 5 s), and at quiet ones (without deaths or
    objectives nearby). The signal is measured against that: the same change around each death, in favour of whoever
    kills. With one match out of every `one_in` (by crc32, so it is always the same sample)."""
    replays = sorted(p.name.split(".")[0] for p in harvest.glob("*.state.csv.gz"))
    chosen = {p for p in replays if zlib.crc32(p.encode()) % one_in == 0}
    pairs = [(r, str(harvest / f"{p}.state.csv.gz"), str(harvest / f"{p}.events.json.gz"))
             for p, r in W.records(games, chosen).items()]
    print(f"# Background noise of the per-second WP · {len(pairs)} games (one in every {one_in})\n", flush=True)
    with ProcessPoolExecutor(processes) as pool:
        curves = [c for c in pool.map(_one_for_noise, pairs, chunksize=4) if "error" not in c]

    rows, per_minute = {}, {}
    for width in WIDTHS:
        for stretch in SEPARATIONS:
            null_, quiet, signal, phase = [], [], [], []
            for c in curves:
                t, z = c["t"], c["z"].astype(float)
                if len(t) < 400:
                    continue
                inst = np.arange(t[0] + 60, t[-1] - 60 - stretch, 5.0)
                d = NEUTRAL * (_means(t, z, inst + stretch + 1, inst + stretch + 1 + width)
                               - _means(t, z, inst - width, inst))
                something = np.array([tm for tm, _s in c["deaths"]] + c["objectives"])
                near = (np.abs(something[None, :] - (inst[:, None] + stretch / 2)) <= stretch / 2 + width + 5).any(1) \
                    if len(something) else np.zeros(len(inst), bool)
                null_.append(d[~np.isnan(d)])
                phase.append(np.searchsorted(PHASES, inst[~np.isnan(d)] / 60, side="right") - 1)
                quiet.append(d[~near & ~np.isnan(d)])
                tm = np.array([m for m, _s in c["deaths"]])
                if len(tm):
                    s = np.array([s for _m, s in c["deaths"]])
                    v = s * NEUTRAL * (_means(t, z, tm + stretch + 1, tm + stretch + 1 + width) - _means(t, z, tm - width, tm))
                    signal.append(v[~np.isnan(v)])
            null_, quiet, signal, phase = (np.concatenate(v) for v in (null_, quiet, signal, phase))
            rows[width, stretch] = (null_.std(), quiet.std(), np.abs(quiet).mean(), signal.mean(), len(signal))
            per_minute[width, stretch] = np.array([null_[phase == p].std() for p in range(len(PHASES))])

    print("Standard deviation of the change between the window before and the one after, in neutral WP points, at")
    print("any instant (and in quiet ones). The signal is the same change around a death, in favour")
    print("of whoever kills, and the signal/noise ratio divides it by the deviation of any instant.\n")
    print("| width (s) | separation (s) | noise | quiet noise | mean |quiet| | death signal | signal/noise "
          "|\n|---|---|---|---|---|---|---|")
    for (width, stretch), (n, tq, atq, s, _k) in rows.items():
        print(f"| {width} | {stretch} | {n:.2f} | {tq:.2f} | {atq:.2f} | {s:+.2f} | {s / n:.2f} |")
    print(f"\nThe noise (any instant) with windows of {WINDOW} s, by stretch of the match: it grows with the minute.\n")
    print("| separation (s) | " + " | ".join(W.stretch(p) for p in range(len(PHASES))) + " |\n|---|" + "---|" * len(PHASES))
    for stretch in SEPARATIONS:
        print(f"| {stretch} | " + " | ".join(f"{v:.2f}" for v in per_minute[WINDOW, stretch]) + " |")
    np.savez_compressed(output / "noise.npz", **{f"{a}_{b}": np.array(v) for (a, b), v in rows.items()},
                        **{f"{a}_{b}_minute": v for (a, b), v in per_minute.items()})


# ── The value of each situation and whose it is ──────────────────────────────

WINDOW = 5  # seconds of each window: see `noise` and value.md

# When each situation of each table starts and ends. The value is the change in its team's WP between the
# window before, [starts - WINDOW, starts), and the one after, (ends, ends + WINDOW].
SPAN = {
    "roams": lambda f: (f["time"], f["time"] + f["lasts"]),
    "flashes": lambda f: (f["time"], f["time"] + 5.0),  # moments.flashes's `kill`: what is decided in 5 s
    "fights": lambda f: (f["since"], f["until"] + 3.0),  # moments.fights counts the deaths up to 3 s later
    "backs": lambda f: (f["time"], f["time"] + 60.0),  # moments.backs's `horizon` for the CS that escapes
    "trades": lambda f: (f["time"], f["time"] + f["lasts"] + 4.0),  # moments.tradeos: whoever dies up to 4 s later
    "departures": lambda f: (f["since"], f["until"]),
    "sidelanes": lambda f: (f["since"], f["until"]),
    "recalls": lambda f: (f["time"], f["time"] + 8.0),  # how long the recall lasts
    # an objective, from when it starts being set up (`LEAD` s before it falls) until it falls
    "setups": lambda f: (f["time"] - LEAD, f["time"]),
}
LEAD = 90.0  # seconds before an objective falls in which it is set up: moments.setups's `before`


def _flash(events: dict, rows) -> tuple[dict, dict[str, str | None]]:
    """(each champion's row at each second, the column that says whether they have flash ready: `d_ready` if they
    carry it in the first spell, slot 4, and `f_ready` if in the second; None if they don't carry it)."""
    return M._table(events, rows), {
        p["champion"]: "d_ready" if s.get("SUMMONER_SPELL_1") == "4" else "f_ready" if s.get("SUMMONER_SPELL_2") == "4" else None
        for p, s in zip(events["players"], events["stats"], strict=True)}


def _windows(c: dict, starts, ends, width: float = WINDOW) -> tuple[np.ndarray, np.ndarray]:
    """(before, after): the mean of blue's log-odds (column 0) and of what each champion contributes (the rest) in
    the window before and the one after each situation. nan if the window falls outside the curve."""
    t = c["t"]
    v = np.column_stack([c["z"], c["contribution"]])
    running = np.vstack([np.zeros(v.shape[1]), np.cumsum(v, axis=0)])
    starts, ends = np.asarray(starts, float), np.asarray(ends, float)

    def mean(i, j):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where((j > i)[:, None], (running[j] - running[i]) / (j - i)[:, None], np.nan)

    return (mean(np.searchsorted(t, starts - width), np.searchsorted(t, starts)),
            mean(np.searchsorted(t, ends, "right"), np.searchsorted(t, ends + width, "right")))


def split(value: float, own: dict[str, float]) -> dict[str, float]:
    """A situation's value for a team, among those of theirs who play it: each one keeps what their own part
    changed (their gold, their XP, their health, whether they die and how long they take to return) and the rest —what the
    enemy lost, what the absent player's was and the objectives— is split in equal parts. It adds up to `value`."""
    rest = (value - sum(own.values())) / len(own)
    return {c: v + rest for c, v in own.items()}


def annotate(concepts: dict[str, list[dict]], c: dict, events: dict, rows) -> None:
    """Adds to each row of the `SPAN` tables its value (`value`, neutral WP points of its team, with
    `wp_before` and `wp_after`, the real WP) and whom it is attributed to:

    - what one alone decides (flash, back, departure, side-lane turn, recall): entirely theirs;
    - fights and trades: `split` among those of each team who take part. Fights belong to both teams: their
      value is blue's (`value_100`; red's, the opposite) and `credit` carries the ten who take part;
    - roams: `value_marksman` is what changes in the lane —the marksman's minus the enemy marksman's— and
      `value_support`, everything else, what the team gains (or loses) on the map. They add up to `value`;
    - setups (the objective, per team) are not split: they carry the state on arrival (`gold_team`, `alive`) and
      `no_flash`, how many of their living arrive without flash ready, to measure what it costs."""
    column = {n: i + 1 for i, n in enumerate(c["champion"])}
    table_of, slot = _flash(events, rows)
    gold, alive = W.ALL_FEATURES.index("gold_k"), W.ALL_FEATURES.index("dead")
    team_of = dict(zip(c["champion"], c["team"], strict=True))
    marksman = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "BOTTOM"}
    for table, stretch in SPAN.items():
        rows = concepts.get(table) or []
        if not rows:
            continue
        before, after = _windows(c, *np.array([stretch(f) for f in rows], float).T)
        change = NEUTRAL * (after - before)  # blue's log-odds' and each champion's for their team
        suffix = "_100" if table == "fights" else ""
        for k, f in enumerate(rows):
            team = "100" if table == "fights" else f.get("team") or team_of[f["champion"]]
            s = 1.0 if team == "100" else -1.0
            if np.isnan(change[k, 0]):
                f |= {f"wp_before{suffix}": "", f"wp_after{suffix}": "", f"value{suffix}": ""}
                continue
            f[f"wp_before{suffix}"] = round(100 / (1 + math.exp(-s * before[k, 0])), 1)
            f[f"wp_after{suffix}"] = round(100 / (1 + math.exp(-s * after[k, 0])), 1)
            f[f"value{suffix}"] = value = s * change[k, 0]
            if table == "roams":
                rival = marksman.get("200" if team == "100" else "100")
                botlane = change[k, column[f["marksman"]]] - (change[k, column[rival]] if rival else 0.0)
                f |= {"value_marksman": botlane, "value_support": value - botlane}
            elif table == "setups":
                arrives = int(f["time"] - LEAD)
                i = _at(c, arrives)
                f |= {"gold_team": round(s * c["x"][i, gold], 2), "alive": int(s * c["x"][i, alive]),
                      "no_flash": sum(1 for q, eq in team_of.items() if eq == team and slot[q]
                                       and (g := table_of[q].get(arrives)) and g["alive"] == "True"
                                       and g[slot[q]] != "True")}
            elif table == "fights":
                parts = {}
                for eq, sign in (("100", 1.0), ("200", -1.0)):
                    own_items = [q for q in f["who"] if team_of[q] == eq]
                    parts |= split(sign * value, {q: change[k, column[q]] for q in own_items})
                f["credit"] = "|".join(f"{q}:{v:+.2f}" for q, v in parts.items())
        if table == "trades":  # one row per champion: the trade is (lane, time), and is split per team
            together: dict[tuple, list[int]] = {}
            for k, f in enumerate(rows):
                together.setdefault((f["lane"], f["time"], team_of[f["champion"]]), []).append(k)
            for ks in together.values():
                if rows[ks[0]]["value"] == "":
                    continue
                parts = split(rows[ks[0]]["value"], {rows[k]["champion"]: change[k, column[rows[k]["champion"]]]
                                                         for k in ks})
                for k in ks:
                    rows[k]["credit"] = parts[rows[k]["champion"]]


def _at(c: dict, second: float) -> int:
    """The index into the curve of the last second with data up to `second`."""
    return max(0, int(np.searchsorted(c["t"], second, "right")) - 1)


def _health(row) -> float | str:
    v = M._health(row)
    return round(min(1.0, max(0.0, v)), 2) if v is not None else ""


HORIZONS = (30, 60, 90)  # seconds after the decision at which the value is looked at


def _prior(c: dict, t: float) -> float:
    """The value of the 30 s before `t` for blue: from the window [t - 35, t - 30) to the one before `t`, the
    same one used to measure what happens afterwards. If the state captures what matters, those who do one thing and
    those who do the other should arrive equal."""
    a, d = _windows(c, [t - 30.0], [t - WINDOW - 0.5])
    return NEUTRAL * (d[0, 0] - a[0, 0])


def roam_decisions(c: dict, events: dict, rows, every: int = 10, before_: int = 30, close: float = 1500.0,
                    far: float = 3000.0, gap: int = 2) -> list[dict]:
    """The support in the laning phase, each time they decide whether to stay with their marksman or leave: the table to
    compare what happens when they leave with what happens when they stay in the same game state.

    - **leaves** (`leaves` = 1): the last second with them within `close` in the `before_` seconds before
      each time they move more than `far` away (the runs of `moments.roams`, with both alive and forgiving
      `gap`), however long it lasts. `lasts` is how long they are away, `short` whether the run ends because the marksman
      or the support dies, and `to_where`, the support's lane in the middle of the run. Those of 15 s or more are the
      roams of `moments.roams`; the others are short visits, or roams that end badly right away and that `moments.roams` doesn't
      see because it asks for 15 s with both alive. Those that don't come from being with the marksman (goes back from base and
      leaves for mid) aren't there: there is no moment at which they decided to leave them.
    - **stays** (`leaves` = 0): one out of every `every` seconds with them within `close`
      (`moments.with_the_marksman`) after which they don't move away in `before_` seconds.

    For each one, the state (minute, team gold and XP, lane gold —marksman and support against the two
    enemies—, living, both's health and whether the enemy support is in the lane), what happened in the 30 s
    before (`prior_`) and what happens at each `HORIZONS`: the value for the team between the window before
    deciding and the one after the horizon, split into `botlane` (the marksman's minus the enemy marksman's) and
    `map_` (the rest), and whether the marksman or the support dies."""
    table, bases = M._table(events, rows), M._bases(rows)
    column = {n: i for i, n in enumerate(c["champion"])}
    died = {p["champion"]: [e["time"] for e in events["events"] if e["type"] == "Death" and e["net_id"] == p["net_id"]]
             for p in events["players"]}
    gold, xp, alive = (W.ALL_FEATURES.index(r) for r in ("gold_k", "xp_k", "dead"))
    out = []
    for team in ("100", "200"):
        position = {p["position"]: p["champion"] for p in events["players"] if p["team"] == team}
        rival = {p["position"]: p["champion"] for p in events["players"] if p["team"] != team}
        adc, sup, rival_adc, rival_sup = position.get("BOTTOM"), position.get("UTILITY"), rival.get("BOTTOM"), rival.get("UTILITY")
        if not (adc and sup and rival_adc and rival_sup):
            continue
        goes, is_ = M.with_the_marksman(table, bases[team], adc, sup, 120.0, 840.0, far, close)
        departures = []  # (start, duration, cut, where to) of each time they move away
        for streak in M._rafagas(goes, gap):
            t0, t1 = streak[0][0], streak[-1][0]
            mid = M._spot(table[sup].get((t0 + t1) // 2))
            departures.append((t0, t1 - t0 + 1, int(any(t1 - 1 <= m <= t1 + 3 for q in (adc, sup) for m in died[q])),
                            M._lane(*mid) if mid else ""))
        moment_list = [(s, 0, "", "", "") for s in is_
                    if s % every == 0 and not any(s < t0 <= s + before_ for t0, *_r in departures)]
        for t0, lasts, short, to_where in departures:
            if previous_ones := [s for s in is_ if t0 - before_ <= s < t0]:
                moment_list.append((previous_ones[-1], 1, lasts, short, to_where))
        sign = 1.0 if team == "100" else -1.0
        for s, leaves, lasts, short, to_where in sorted(moment_list):
            i = _at(c, s)
            x, own_items = c["x"][i], c["own_items"][i]
            b = M._spot(table[rival_sup].get(s))
            row = {"team": team, "time": s, "leaves": leaves, "lasts": lasts, "short": short, "to_where": to_where,
                    "marksman": adc, "support": sup,
                    "gold_team": round(sign * x[gold], 2), "xp_team": round(sign * x[xp], 2),
                    "gold_botlane": round(float(sum(own_items[column[q], gold] for q in (adc, sup))
                                             - sum(own_items[column[q], gold] for q in (rival_adc, rival_sup))), 2),
                    "alive": int(sign * x[alive]), "health_marksman": _health(table[adc].get(s)),
                    "health_support": _health(table[sup].get(s)),
                    "rival_in_botlane": int(bool(b) and table[rival_sup][s]["alive"] == "True"
                                          and math.dist(b, M._spot(table[adc][s])) <= far),
                    "prior": sign * _prior(c, s)}
            for h in HORIZONS:
                before, after = _windows(c, [s], [s + h])
                change = NEUTRAL * (after[0] - before[0])
                if np.isnan(change[0]):
                    continue
                botlane = change[1 + column[adc]] - change[1 + column[rival_adc]]
                row |= {f"value{h}": sign * change[0], f"botlane{h}": botlane, f"map_{h}": sign * change[0] - botlane,
                         f"dies_{h}": int(any(s < m <= s + h for m in died[adc])),
                         f"dies_support_{h}": int(any(s < m <= s + h for m in died[sup]))}
            out.append(row)
    return out


def flash_decisions(c: dict, events: dict, rows, fight_list: list[dict], flash_list: list[dict],
                     since: float = 840.0, before: float = 4.0) -> list[dict]:
    """Each skirmish past the laning phase (`since`) and each of those playing it with flash ready
    `before` seconds before it starts: the table to compare whoever spends it (`flashes` = 1, with the use from
    `moments.flashes`: objective ones don't enter) with whoever doesn't, in the same state.

    For each one, the state (minute, team gold, living, how many on each side, their health, their position and the
    seconds until the next dragon, 0 if already alive) and what happens: the fight's value for their team
    (`value`) and theirs (`own`), whether they die, and the value from before the fight until after the
    next dragon falls (`value_dragon`), whether their team takes it and whether they reach it with flash ready. And, as in
    `roam_decisions`, what happened in the 30 s before (`prior_`); for whoever flashes, how long their flash takes to
    come back (`cooldown`)."""
    table, slot = _flash(events, rows)
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    net = {p["net_id"]: p for p in events["players"]}
    died = {p["champion"]: [e["time"] for e in events["events"] if e["type"] == "Death" and e["net_id"] == p["net_id"]]
             for p in events["players"]}
    dragons = {round(d["time"], 1): net[d["killer"]]["team"] for d in events["camps"]
                if d["camp"].startswith("Dragon") and d.get("killer") in net}
    timers = M._timers(events)
    column = {n: i for i, n in enumerate(c["champion"])}
    gold, alive = W.ALL_FEATURES.index("gold_k"), W.ALL_FEATURES.index("dead")
    out = []
    for fight in fight_list:
        if fight["teamfight"] or fight["since"] < since:
            continue
        t0, t1 = fight["since"], fight["until"] + 3.0
        spawns_at, falls_, _n = min(((a, k, n) for a, k, n in timers if k > t0), default=(math.inf, math.inf, ""))
        i = _at(c, t0 - before)
        for q in fight["who"]:
            ready = table[q].get(int(t0 - before))
            if not slot[q] or not ready or ready[slot[q]] != "True":
                continue
            flash = next((f for f in flash_list if f["champion"] == q and t0 - 3 <= f["time"] <= fight["until"] + 1), None)
            if flash and flash["use"] != "skirmish":
                continue
            eq = team_of[q]
            sign = 1.0 if eq == "100" else -1.0
            own_ones = sum(team_of[o] == eq for o in fight["who"])
            here = M._spot(table[q].get(int(t0)))
            near = sum(1 for o, e2 in team_of.items() if e2 != eq and here and (g := table[o].get(int(t0)))
                        and g["alive"] == "True" and (b := M._spot(g)) and math.dist(here, b) <= W.FIGHT)
            row = {"team": eq, "champion": q, "position": next(p["position"] for p in events["players"] if p["champion"] == q),
                    "time": t0, "flashes": int(bool(flash)), "suboptimal": flash["suboptimal"] if flash else "",
                    "cooldown": flash["cooldown"] if flash else "",
                    "to_dragon": round(max(spawns_at - t0, 0.0)) if spawns_at < math.inf else "",
                    "own_ones": own_ones, "rivals": len(fight["who"]) - own_ones, "rivals_near": near,
                    "gold_team": round(sign * c["x"][i, gold], 2), "alive": int(sign * c["x"][i, alive]),
                    "health": _health(ready), "died": int(any(t0 <= m <= t1 for m in died[q])),
                    "prior": sign * _prior(c, t0)}
            a, d = _windows(c, [t0], [t1])
            change = NEUTRAL * (d[0] - a[0])
            if not np.isnan(change[0]):
                row |= {"value": sign * change[0], "own": change[1 + column[q]]}
            if falls_ < math.inf:
                a, d = _windows(c, [t0], [falls_])
                if not np.isnan(d[0, 0] - a[0, 0]):
                    row["value_dragon"] = NEUTRAL * sign * (d[0, 0] - a[0, 0])
                who = dragons.get(round(falls_, 1))
                row["dragon_own"] = int(who == eq) if who else ""
                at_dragon = table[q].get(int(falls_))
                row["flash_in_dragon"] = int(at_dragon[slot[q]] == "True") if at_dragon else ""
            out.append(row)
    return out


# ── Mistake or not? ───────────────────────────────────────────────────────────


def _read(path: Path) -> dict[str, np.ndarray]:
    """A features CSV by columns: numbers where possible (nan for blank), text where not."""
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for k in rows[0]:
        try:
            out[k] = np.array([float(f[k]) if f[k] != "" else np.nan for f in rows])
        except ValueError:
            out[k] = np.array([f[k] for f in rows])
    return out


def effect(treated: np.ndarray, y: np.ndarray, stratum: np.ndarray, game: np.ndarray,
           times: int = 200) -> tuple[float, float, float, float]:
    """(effect, 90% interval, share of the treated that has someone to be compared with).

    The mean effect on the treated by strata: in each stratum (a combination of game state), the
    mean of the treated minus that of the controls, weighted by how many treated it has. Only strata with
    both count. The interval resamples whole matches, since the situations of a match aren't
    independent (they share a result and often the same fight)."""
    ok = ~np.isnan(y)
    if not (treated[ok] == 1).any() or not (treated[ok] == 0).any():
        return (math.nan,) * 4
    treated, y, stratum, game = treated[ok].astype(int), y[ok], stratum[ok], game[ok]
    stratum = np.unique(stratum, return_inverse=True)[1]
    cells = 2 * (stratum.max() + 1)
    _, game = np.unique(game, return_inverse=True)

    def one_(weight: np.ndarray) -> tuple[float, float]:
        n = np.bincount(2 * stratum + treated, weight, cells).reshape(-1, 2)
        s = np.bincount(2 * stratum + treated, weight * y, cells).reshape(-1, 2)
        valid = (n > 0).all(axis=1)
        m = s[valid] / n[valid]
        with np.errstate(invalid="ignore"):  # with no stratum with both: nan
            return float((n[valid, 1] * (m[:, 1] - m[:, 0])).sum() / n[valid, 1].sum()), n[valid, 1].sum() / n[:, 1].sum()

    base, covers = one_(np.ones(len(y)))
    rng = np.random.default_rng(0)
    times_of = [np.bincount(rng.integers(game.max() + 1, size=game.max() + 1), minlength=game.max() + 1)
                for _ in range(times)]
    others_ = [one_(v[game].astype(float))[0] for v in times_of]
    return base, float(np.percentile(others_, 5)), float(np.percentile(others_, 95)), covers


def _spans(v: np.ndarray, cuts: tuple[float, ...]) -> np.ndarray:
    return np.digitize(np.nan_to_num(v, nan=-1e9), cuts)


def _stratum(*columns: np.ndarray) -> np.ndarray:
    return np.unique(np.column_stack(columns), axis=0, return_inverse=True)[1].ravel()


def _cell(e: tuple[float, float, float, float]) -> str:
    base, lo, hi, _covers = e
    return f"{base:+.2f} [{lo:+.2f}, {hi:+.2f}]"


# (title, query) of what each situation is worth, on average, and how it is split; {c} is the features folder
SUMMARY = (
    ("All tables: value for the team of the situation (in fights, for blue, and that is why the mean of |value|)",
     " union all ".join(f"select '{t}' table_name, count(*) n_rows, count({v}) with_value, avg({v}) mean, "
                        f"stddev({v}) deviation, avg(abs({v})) mean_abs from '{{c}}/{t}.csv'"
                        for t, v in [(t, "value_100" if t == "fights" else "value") for t in SPAN])),
    ("Roams: what changes in the botlane (marksman) and on the map (support)",
     "select deaths > 0 marksman_dies, count(*) roams, avg(value) value, avg(value_marksman) marksman, "
     "avg(value_support) support from '{c}/roams.csv' group by all order by all"),
    ("Flashes, by use",
     "select use, suboptimal, count(*) flashes, avg(value) value, avg(offensive) offensive from "
     "'{c}/flashes.csv' group by all order by all"),
    ("Fights: value for the team that loses fewer champions",
     "select teamfight, count(*) fights, avg(case when deaths_200 > deaths_100 then value_100 else -value_100 "
     "end) value from '{c}/fights.csv' where deaths_100 != deaths_200 group by all order by all"),
    ("Backs, by the moment of the wave",
     "select kind, count(*) backs, avg(cs_lost) cs_lost, avg(value) value from '{c}/backs.csv' group by all "
     "order by all"),
    ("Trades: each one's credit, depending on whether they die",
     "select dies, count(*) n_rows, avg(value) trade_value, avg(credit) credit from '{c}/trades.csv' group by "
     "all order by all"),
    ("Recalls",
     "select cancelled, cut_short, count(*) recalls, avg(value) value from '{c}/recalls.csv' group by all order by all"),
    ("Objectives: value for whoever takes them",
     "select split_part(objective, ' ', 1) objective, count(*) times, avg(value) value from '{c}/setups.csv' "
     "where takes_it = 1 group by all order by all"),
)


def summary(folder: Path) -> None:
    """The means of `SUMMARY`, in markdown."""
    for title, query in SUMMARY:
        r = duckdb.sql(query.format(c=folder.as_posix()))
        print(f"### {title}\n\n| " + " | ".join(r.columns) + " |\n|" + "---|" * len(r.columns))
        for row in r.fetchall():
            print("| " + " | ".join(f"{v:,.2f}" if isinstance(v, float) else f"{v:,d}" if isinstance(v, int)
                                    else "—" if v is None else str(v) for v in row) + " |")
        print()
    if not (path := MODEL_FILE.parent / "noise.npz").exists():
        return
    # how much of what a situation's value varies is its own: the noise of any pair of windows
    # separated by how long each lasts (from `noise`, interpolated) against how much it really varies
    r = np.load(path)
    noise2 = np.array([r[f"{WINDOW}_{s}_minute"] ** 2 for s in SEPARATIONS])  # (separation, stretch of the match)
    print("### How much of what the value varies is the situation's and how much is noise\n")
    print(f"The noise, from `noise` with windows of {WINDOW} s and in the same stretch of the match; beyond 60 s of "
          "separation the 60 s one is taken, which falls short.\n")
    print("| table | how long it lasts (median, s) | deviation of the value | that of any two equally "
          "separated windows | share that is not noise |\n|---|---|---|---|---|")
    for table, stretch in SPAN.items():
        f = _read(folder / f"{table}.csv")
        v = f["value_100" if table == "fights" else "value"]
        ok = ~np.isnan(v)
        starts, ends = stretch(f)
        phase = np.searchsorted(PHASES, starts[ok] / 60, side="right") - 1
        expected = np.sqrt(np.mean([np.interp(d, SEPARATIONS, noise2[:, p])
                                    for d, p in zip(ends[ok] - starts[ok], phase, strict=True)]))
        print(f"| {table} | {np.median((ends - starts)[ok]):.0f} | {v[ok].std():.2f} | {expected:.2f} | "
              f"{max(0.0, 1 - expected ** 2 / v[ok].var()):.0%} |")
    print()


def _groups(league: np.ndarray, adds_up: np.ndarray):
    """(name, rows) of each league, of all, and of all the matches that match their statsJson."""
    yield from ((LEAGUES[g], league == g) for g in range(len(LEAGUES)))
    yield "**all**", np.ones(len(league), bool)
    yield "all, only those that add up", adds_up == 1


def effects(folder: Path) -> None:
    """What each situation is worth (`summary`), and the support's roam and the suboptimal flash against what was done in
    similar situations (`effect`), by league."""
    print("# What each situation is worth and whose it is\n\n## What each thing is worth, on average (neutral WP points)\n")
    summary(folder)
    r = _read(folder / "roam_decisions.csv")
    for h in HORIZONS:  # in percentage points
        r[f"dies_{h}"], r[f"dies_support_{h}"] = 100 * r[f"dies_{h}"], 100 * r[f"dies_support_{h}"]
    league = np.array([LEAGUES.index(v) for v in r["league"]])
    # the state in which they decide: league, minute (in steps of 2), team and lane gold, living, whether the enemy
    # support is in the lane and the marksman's health
    state = _stratum(league, _spans(r["time"], (240, 360, 480, 600, 720)),
                      _spans(r["gold_team"], (-1.5, -0.5, 0.5, 1.5)), _spans(r["gold_botlane"], (-0.5, 0.5)),
                      np.sign(r["alive"]), r["rival_in_botlane"], _spans(r["health_marksman"], (0.5, 0.8)))
    league_only = _stratum(league, _spans(r["time"], (240, 360, 480, 600, 720)))
    stays, leaves = r["leaves"] == 0, r["leaves"] == 1
    long_ones, cut_ones = leaves & (r["lasts"] >= 15), leaves & (r["lasts"] < 15) & (r["short"] == 1)
    # the roam being compared: those of moments.roams (15 s or more) and those that end badly earlier, which moments.roams
    # doesn't see because it asks for 15 s with both alive. Without them, roams would be only those that survive.
    roam = long_ones | cut_ones

    def compares(treated_ones: np.ndarray, m: np.ndarray, column: str, strata: np.ndarray = state):
        used = m & (treated_ones | stays)
        return effect(treated_ones[used].astype(float), r[column][used], strata[used], r["game"][used])

    print("## Support roam: leaving against staying with the marksman\n")
    print(f"{int(leaves.sum()):,d} times the support leaves their marksman in the laning phase (from being within 1500 to "
          f"beyond 3000): {int(long_ones.sum()):,d} of 15 s or more, {int(cut_ones.sum()):,d} shorter ones that end with a "
          f"death of the marksman or the support, and {int((leaves & ~roam).sum()):,d} short visits. And "
          f"{int(stays.sum()):,d} moments in which they stay. From {len(set(r['game'])):,d} games.\n")
    print("Neutral WP points for the support's team, leaving minus staying, in the same state. `prior`: the "
          "same with the 30 s before deciding, which should not distinguish them.\n")
    print("### What counts as a roam (all leagues)\n")
    print("| roams | how many | prior | balance at 30 s | at 60 s | at 90 s | marksman dies at 30 s (pp) "
          "|\n|---|---|---|---|---|---|---|")
    all_ = np.ones(len(league), bool)
    for name, t in (("15 s or more (those of `moments.roams`)", long_ones),
                      ("**15 s or more, or cut short by a death** (the one that is used)", roam),
                      ("any departure, even of 2 s", leaves)):
        print(f"| {name} | {int(t.sum()):,d} | {_cell(compares(t, all_, 'prior'))} | "
              + " | ".join(_cell(compares(t, all_, f"value{h}")) for h in HORIZONS)
              + f" | {_cell(compares(t, all_, 'dies_30'))} |")

    def row(name: str, m: np.ndarray, h: int, without_strata: bool = True) -> str:
        net = compares(roam, m, f"value{h}")
        return (f"| {name} | {int((roam & m).sum()):,d} | {_cell(compares(roam, m, 'prior'))} | "
                + (f"{_cell(compares(roam, m, f'value{h}', league_only))} | " if without_strata else "")
                + f"{_cell(net)} | {_cell(compares(roam, m, f'botlane{h}'))} | {_cell(compares(roam, m, f'map_{h}'))} | "
                  f"{_cell(compares(roam, m, f'dies_{h}'))} | {net[3]:.0%} |")

    for h in (60, 30):
        print(f"\n### By league, at {h} s\n")
        print("`botlane`: the marksman's part minus the rival marksman's; `map`: everything else.\n")
        print("| league | roams | prior | no strata (only league and minute) | net balance | botlane | map | "
              "marksman dies (pp) | comparable |\n|---|---|---|---|---|---|---|---|---|")
        for name, m in _groups(league, r["adds_up"]):
            print(row(name, m, h))
    print("\n### According to where it goes and whether the rival support stays in the botlane (all leagues, at 60 s)\n")
    print("| roams | how many | prior | net balance | botlane | map | marksman dies (pp) | comparable "
          "|\n|---|---|---|---|---|---|---|---|")
    for dest in ("mid", "top", "bot"):
        print(row(f"a {dest}", stays | (r["to_where"] == dest), 60, without_strata=False))
    for rival, text in ((1, "with the rival support in the botlane"), (0, "with the rival support out")):
        print(row(text, r["rival_in_botlane"] == rival, 60, without_strata=False))
    sup_dies = compares(roam, all_, "dies_support_60")
    print(f"\nThe support who leaves dies in the following 60 s {_cell(sup_dies)} percentage points more than the one who "
          "stays.\n")

    f = everyone = _read(folder / "flash_decisions.csv")
    f["after"] = f["value_dragon"] - f["value"]  # from after the fight to after the dragon: the deferred cost
    # the suboptimal flash of moments.flashes: in a skirmish with the next dragon before it comes back. The
    # controls, with flash ready and not spent, in skirmishes with the dragon within 5 min (how long it takes to
    # come back without reduction)
    use = ((f["flashes"] == 1) & (f["suboptimal"] == 1)) | ((f["flashes"] == 0) & (f["to_dragon"] < 300))
    f = {k: v[use] for k, v in f.items()}
    league = np.array([LEAGUES.index(v) for v in f["league"]])
    state = _stratum(league, _spans(f["time"], (1200, 1500, 1800)), _spans(f["gold_team"], (-3, -1, 1, 3)),
                      np.sign(f["alive"]), np.sign(f["own_ones"] - f["rivals"]), _spans(f["health"], (0.35, 0.7)),
                      _spans(f["rivals_near"], (2, 3)), _spans(f["to_dragon"], (1, 90, 180)))
    league_only = _stratum(league, _spans(f["time"], (1200, 1500, 1800)))
    print("## Suboptimal flash: spending it in a skirmish with the dragon on the way, against keeping it\n")
    print(f"{int(f['flashes'].sum()):,d} suboptimal flashes in skirmishes and {int((f['flashes'] == 0).sum()):,d} "
          f"players with flash ready who do not spend it in the skirmish, from {len(set(f['game'])):,d} games.\n")
    print("Neutral WP points (and percentage points in `dies` and `own dragon`), flashing minus not flashing. "
          "`prior`: the 30 s before the fight; `from the fight to the dragon`: from after the fight to after "
          "the next dragon falls, the deferred cost.\n")
    print("| league | flashes | prior | fight, no strata | fight | their own | dies (pp) | from the fight to "
          "the dragon | own dragon (pp) | comparable |\n|---|---|---|---|---|---|---|---|---|---|")
    groups = [*_groups(league, f["adds_up"]), *((f"**all**, {p}", f["position"] == p) for p in
                                            ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"))]
    for name, m in groups:
        t, e, p = f["flashes"][m], state[m], f["game"][m]
        fight = effect(t, f["value"][m], e, p)
        print(f"| {name} | {int(t.sum()):,d} | {_cell(effect(t, f['prior'][m], e, p))} | "
              f"{_cell(effect(t, f['value'][m], league_only[m], p))} | {_cell(fight)} | "
              f"{_cell(effect(t, f['own'][m], e, p))} | {_cell(effect(t, 100 * f['died'][m], e, p))} | "
              f"{_cell(effect(t, f['after'][m], e, p))} | "
              f"{_cell(effect(t, 100 * f['dragon_own'][m], e, p))} | {fight[3]:.0%} |")

    # the deferred cost, without the selection of who flashes: among those who spend it in a skirmish, those who
    # end up without it for the dragon by a little against those who recover it by a little (within ±90 s of how long theirs
    # takes to come back). Both groups made the same decision; what changes is whether they reach the dragon with flash.
    f = everyone
    margin = f["to_dragon"] - f["cooldown"]  # negative: the dragon spawns before it comes back
    f = {k: v[(f["flashes"] == 1) & (np.abs(margin) <= 90)] for k, v in f.items()}
    no_flash_left = (f["to_dragon"] < f["cooldown"]).astype(float)
    league = np.array([LEAGUES.index(v) for v in f["league"]])
    state = _stratum(league, _spans(f["time"], (1200, 1500, 1800)), _spans(f["gold_team"], (-3, -1, 1, 3)),
                      np.sign(f["alive"]))
    print("\n### The deferred cost: spent shortly before or shortly after it comes back for the dragon\n")
    print(f"Only whoever spends it in a skirmish, with the dragon less than 90 s from when the flash comes back: "
          f"{int(no_flash_left.sum()):,d} are left without it for the dragon and {int((no_flash_left == 0).sum()):,d} recover it. With flash "
          f"when the dragon falls: {np.nanmean(f['flash_in_dragon'][no_flash_left == 1]):.0%} of the former and "
          f"{np.nanmean(f['flash_in_dragon'][no_flash_left == 0]):.0%} of the latter.\n")
    print("| league | without flash for the dragon | prior | fight | from the fight to the dragon | own "
          "dragon (pp) | comparable |")
    for name, m in _groups(league, f["adds_up"]):
        t, e, p = no_flash_left[m], state[m], f["game"][m]
        carries = effect(t, 100 * f["dragon_own"][m], e, p)
        print(f"| {name} | {int(t.sum()):,d} | {_cell(effect(t, f['prior'][m], e, p))} | "
              f"{_cell(effect(t, f['value'][m], e, p))} | {_cell(effect(t, f['after'][m], e, p))} | {_cell(carries)} | "
              f"{carries[3]:.0%} |")

    # what it costs afterwards: reaching a dragon with more players without flash than the enemy, against reaching it equal
    s = _read(folder / "setups.csv")
    rival = {(p, o, t, e): n for p, o, t, e, n in zip(s["game"], s["objective"], s["time"], s["team"], s["no_flash"], strict=True)}
    extra = np.array([n - rival.get((p, o, t, 300 - e), np.nan)
                       for p, o, t, e, n in zip(s["game"], s["objective"], s["time"], s["team"], s["no_flash"], strict=True)])
    use = np.char.startswith(s["objective"].astype(str), "Dragon") & (s["time"] >= 840) & (extra >= 0)
    s, extra = {k: v[use] for k, v in s.items()}, extra[use]
    league = np.array([LEAGUES.index(v) for v in s["league"]])
    state = _stratum(league, _spans(s["time"], (1200, 1500, 1800)), _spans(s["gold_team"], (-3, -1, 1, 3)),
                      np.sign(s["alive"]))
    treated = (extra >= 1).astype(float)
    print("\n## Arriving at a dragon with more players without flash than the rival (from minute 14)\n")
    print(f"{int(treated.sum()):,d} arrivals with more without flash than the rival and {int((treated == 0).sum()):,d} with the "
          f"same, {LEAD:.0f} s before it falls.\n")
    print("| league | arrivals with fewer flashes | takes it, no strata (pp) | takes it (pp) | dragon value | "
          "comparable |\n|---|---|---|---|---|---|")
    groups = [*_groups(league, s["adds_up"]), ("**all**, one more without flash", extra <= 1),
              ("**all**, two or more", (extra == 0) | (extra >= 2))]
    for name, m in groups:
        carries = effect(treated[m], 100 * s["takes_it"][m], state[m], s["game"][m])
        print(f"| {name} | {int(treated[m].sum()):,d} | "
              f"{_cell(effect(treated[m], 100 * s['takes_it'][m], league[m], s['game'][m]))} | {_cell(carries)} | "
              f"{_cell(effect(treated[m], s['value'][m], state[m], s['game'][m]))} | {carries[3]:.0%} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # redirected to a file, Windows would write in cp1252
    # a stratum with one treated (5) and two controls (1 and 3), and another with only controls: the effect is 5 - 2
    assert effect(np.array([1, 0, 0, 0]), np.array([5.0, 1.0, 3.0, 9.0]), np.array([0, 0, 0, 1]),
                  np.array([0, 1, 2, 3]), times=2)[::3] == (3.0, 1.0)
    assert split(3.0, {"a": 2.0, "b": -1.0}) == {"a": 3.0, "b": 0.0}  # each one's own, and the rest evenly
    # the weights blended at one second give the same log-odds as wp_per_second.logits
    coefs = np.array([[float(p), 1.0] for p in range(len(PHASES))])
    x, minute = np.array([[2.0], [3.0]]), np.array([12.5, 15.0])
    w = weights_at(minute, coefs)
    assert np.allclose(w[:, 0] + (w[:, 1:] * x).sum(1), W.logits(list(coefs), x, minute, smooth=True))
    order, *rest = sys.argv[1:]
    processes = int(rest[rest.index("--processes") + 1]) if "--processes" in rest else 3
    if order == "model":
        model(Path(rest[0]), Path(rest[1]))
    elif order == "effects":
        effects(Path(rest[0]))
    elif order == "noise":
        output = Path(rest[2])
        output.mkdir(parents=True, exist_ok=True)
        noise(Path(rest[0]), Path(rest[1]), output, processes)


if __name__ == "__main__":
    main()
