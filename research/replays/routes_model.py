"""The scikit-learn part of `routes.py`: which routes junglers choose at each moment and how much each yields.

It is called from `routes.py analyse` and `routes.py game`. It needs `decisions.csv.gz` (from `routes.py merge`), the
harvest's `wp_per_second.npz` and `value.py`'s `model.json` (the per-second WP from Phase 3).

**A route's value, adjusted for the state.** That those who gank bot win more WP says nothing if bot is ganked
when bot is already winning. So, for each outcome (their team's WP, whether the jungler dies, the gold against the
enemy jungler), a model learns **without the route** what usually happens after a state like that, validated by match (each
decision is predicted with a model that has not seen its match). What a route yields is the mean of what came out minus
what was expected: the route's WPA above its state. The interval is 90%, resampling whole matches.
Since what is expected isn't calibrated in all states (see `centre`), each residual is compared with those of its cell:
the moment and the health and gold state.

**Three horizons**: 90 s, 3 min and 5 min. At 90 s the immediate is seen (the gank, the fight, the time lost
on going back to base); at 3 and 5 min, also what going back buys or what the enemy stops doing after being invaded. The
longer, the more things happen that have nothing to do with the route, so the interval widens.

**The counter-gank**: the gank to a lane where the enemy jungler already was (`routes._route`). To value it, the decisions in which
the enemy jungler planted themselves in a lane in the following 30 s are compared (`rival_ganks`, which the player
doesn't know and which enters no model): whoever went to that lane against whoever carried on with their own.

**The routes in a specific state** (`game`): another model learns which route Master-and-above junglers choose
in each state (the policy, only with what the player could know). For each decision in a match, the
routes chosen by at least 5% of the high league in that state are shown, with what each is worth in the finest cell that has
plenty of cases (`values`, `_keys`): state-by-state value isn't learned yet with 5,000 matches. A route that
almost nobody chooses there has nothing to be compared with.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

NEUTRAL = 100 / 4  # WP points per log-odds point at 50%, like value.py
LEAGUES = ("GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER")
HIGH = (4, 5, 6)
MINIMUM = 0.05  # share of the high league that must choose a route in that state to value it
OMNISCIENT = ("rival_half_real", "rival_clean", "rival_lane_real", "rival_ganks")  # they didn't know it: out
CATEGORICAL = ("jungler", "rival_jungler", "after", "half_now", "rival_seen_half", "rival_lane_seen",
               "top_objective_which", "bot_objective_which")
HORIZONS = (90, 180, 300)
NAME_H = {90: "90 s", 180: "3 min", 300: "5 min"}
# the 90 s one keeps the names of the first version (and in the first camp it reaches 3:45)
WP_H = {90: "value_90", 180: "value_180", 300: "value_300"}
DIES_H = {90: "dies_in_horizon", 180: "dies_180", 300: "dies_300"}
GOLD_H = {90: "gold_vs_rival_change", 180: "gold_vs_rival_180", 300: "gold_vs_rival_300"}
OUTCOMES = (*WP_H.values(), *DIES_H.values(), *GOLD_H.values())
BINARY = tuple(DIES_H.values())
FOLDS = 3


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


# ---------------------------------------------------------------- each match's WP every 10 s

def wp(npz: Path, model_json: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(seconds, blue's log-odds) of each harvest match, with the Phase 3 model blending stretches."""
    d = np.load(npz)
    m = json.loads(model_json.read_text(encoding="utf-8"))
    coefs, centres = np.array(m["coefficients"]), np.array(m["centres"])
    x, t = d["x"].astype(float), d["t"].astype(float)
    z = coefs[:, 0][None, :] + x @ coefs[:, 1:].T
    a = np.interp(t / 60, centres, np.arange(len(centres)))
    lo = np.floor(a).astype(int)
    hi = np.minimum(lo + 1, len(centres) - 1)
    r = np.arange(len(x))
    zz = (1 - (a - lo)) * z[r, lo] + (a - lo) * z[r, hi]
    out = {}
    order = np.argsort(d["game"], kind="stable")
    cuts = np.flatnonzero(np.diff(d["game"][order])) + 1
    for chunk in np.split(order, cuts):
        k = int(d["game"][chunk[0]])
        out[str(d["ids"][k]).replace("_", "-")] = (t[chunk], zz[chunk])
    return out


def with_value(df: pd.DataFrame, curves: dict) -> pd.DataFrame:
    """Adds `value_90`, `value_180` and `value_300`: the change in their team's WP between the decision's state and
    each horizon, in neutral WP points (the last state before and the first after: the curve goes every
    10 s). The 90 s one uses the `horizon` column (in the first camp, up to 3:45)."""
    df = df.copy()
    for h, col in WP_H.items():
        hs = df["horizon"] if h == 90 else pd.Series(h, index=df.index)
        values = np.full(len(df), np.nan)
        for i, (pid, t, hh, eq) in enumerate(zip(df["game"], df["t"], hs, df["team"])):
            c = curves.get(pid)
            if c is None or pd.isna(hh):
                continue
            ts, zs = c
            a = max(0, np.searchsorted(ts, t, side="right") - 1)
            b = np.searchsorted(ts, t + hh, side="left")
            if b >= len(ts):
                continue
            values[i] = NEUTRAL * (zs[b] - zs[a]) * (1 if int(eq) == 100 else -1)
        df[col] = values
    return df


# ---------------------------------------------------------------- features and models

def long_route(df: pd.DataFrame) -> pd.Series:
    """The route with its detail where it matters: the camp in the first decisions, the lane in the ganks."""
    det = df["detail"].fillna("").astype(object).astype(str)
    r = df["route"].fillna("nothing").astype(object).astype(str)
    return np.where(r.isin(["gank", "counter_gank"]), r + " " + det,
                    np.where(r.isin(["camp", "invade"]) & (df["decision"] <= 1), r + " " + det, r))


def features(df: pd.DataFrame, categories: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """The state's feature matrix (without what the player didn't know) and the categories of each text column."""
    drop = {"game", "source", "wins", "route", "detail", "route_t", "gold_90", "kills_90", "deaths_90",
              "dies_jungler_90", "objectives_120", "horizon", "league", "long_route", "exam", "moment", "group",
              *OUTCOMES, *OMNISCIENT}
    result = ("res_", "expected_", "centred_", "value", "dies_", "gold_vs_rival_", "xp_vs_rival_")
    X = df[[c for c in df.columns if c not in drop and not c.startswith(result) and c != "league_i"]].copy()
    X["league_i"] = df["league"].map({l: i for i, l in enumerate(LEAGUES)})
    X["level"] = pd.to_numeric(X["level"], errors="coerce").fillna(1)
    categories = dict(categories or {})
    for c in CATEGORICAL:
        text = X[c].fillna("").astype(object).astype(str)  # in pandas 3 a gap remains a gap after astype(str)
        if c not in categories:
            categories[c] = sorted(set(text))[:250]
        X[c] = pd.Categorical(text, categories=categories[c]).codes.astype(float)
        X.loc[X[c] < 0, c] = np.nan
    return X.apply(pd.to_numeric, errors="coerce"), categories


def _cat_mask(X: pd.DataFrame) -> list[bool]:
    return [c in CATEGORICAL for c in X.columns]


# What happens in 90 s is mostly noise: with large trees the model learns the matches and predicts worse than the
# mean (negative out-of-fold R²). With small trees, big leaves and slow learning it stays at +0.02/+0.03,
# which is what can be predicted from 90 s of a match.
SLOW = dict(max_iter=150, learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=1000, l2_regularization=5.0,
             random_state=0)


def _regressor(X, extra: list[bool] | None = None):
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(categorical_features=_cat_mask(X) + (extra or []), **SLOW)


def _classifier(X):
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(categorical_features=_cat_mask(X), **SLOW)


def _policy(X):
    """Which route they choose: here each decision carries its label, so the model can be finer than the outcome ones."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=300,
                                          l2_regularization=1.0, categorical_features=_cat_mask(X), random_state=0)


def _ci(residual: np.ndarray, game: np.ndarray, times: int = 300) -> tuple[float, float]:
    g = pd.DataFrame({"r": residual, "p": game}).groupby("p")["r"].agg(["sum", "count"])
    rng, idx = np.random.default_rng(0), np.arange(len(g))
    means = [g["sum"].to_numpy()[k].sum() / g["count"].to_numpy()[k].sum()
              for k in (rng.choice(idx, len(idx)) for _ in range(times))]
    return float(np.percentile(means, 5)), float(np.percentile(means, 95))


def _expected(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, binary: bool) -> np.ndarray:
    """What is expected in each state without knowing the route, out of fold by match."""
    from sklearn.model_selection import GroupKFold

    pred = np.full(len(y), np.nan)
    ok = ~np.isnan(y)
    idx = np.flatnonzero(ok)
    for tr, te in GroupKFold(FOLDS).split(idx, groups=groups[idx]):
        a, b = idx[tr], idx[te]
        if binary:
            m = _classifier(X).fit(X.iloc[a], y[a].astype(int))
            pred[b] = m.predict_proba(X.iloc[b])[:, 1]
        else:
            m = _regressor(X).fit(X.iloc[a], y[a])
            pred[b] = m.predict(X.iloc[b])
    return pred


# ---------------------------------------------------------------- the report

MOMENTS = [("First camp (on leaving the fountain)", lambda d: d["decision"] == 0),
            ("After the 1st camp", lambda d: d["decision"] == 1),
            ("After the 2nd", lambda d: d["decision"] == 2),
            ("After the 3rd", lambda d: d["decision"] == 3),
            ("After the 4th", lambda d: d["decision"] == 4),
            ("After the 5th", lambda d: d["decision"] == 5),
            ("After the 6th", lambda d: d["decision"] == 6),
            ("From the 7th to 14:00", lambda d: d["decision"] >= 7)]


def _cell(v: np.ndarray, games: np.ndarray, fmt: str, bold: bool = True) -> str:
    """Mean and 90% interval; in bold if the interval doesn't cross zero."""
    ok = ~np.isnan(v)
    if ok.sum() < 30:
        return ""
    lo, hi = _ci(v[ok], games[ok])
    m = fmt.format(v[ok].mean())
    return f"{'**' + m + '**' if bold and (lo > 0 or hi < 0) else m} [{fmt.format(lo)}, {fmt.format(hi)}]"


TABLE_COLUMNS = [(f"centred_{WP_H[h]}", "{:+.2f}") for h in HORIZONS] + \
                 [("centred_dies_in_horizon", "{:+.1%}"), (f"centred_{GOLD_H[300]}", "{:+.0f}")]
TABLE_HEADER = " | ".join(f"WP a {NAME_H[h]}" for h in HORIZONS) + \
                 " | he dies (90 s) | gold against the rival jungler (5 min) |"


def moment_table(d: pd.DataFrame, title: str) -> list[str]:
    """The routes of a moment, with what each yields against the decisions of the same moment and the same health and
    gold state (`centre`; what matters is the difference between routes, not the level), at each horizon."""
    d = d.copy()
    for col, _f in TABLE_COLUMNS:
        d[col] = d[col] - d[col].mean()
    high_ = d["league_i"].isin(HIGH)
    low_ = d["league_i"].isin((0, 1))
    lines = [f"### {title}\n", f"{len(d):,d} decisions from {d['game'].nunique():,d} games.\n",
              f"| route | choose it | Gold-Plat. | Master+ | {TABLE_HEADER}", "|---|---|---|---|---|---|---|---|---|"]
    for route, g in sorted(d.groupby("long_route"), key=lambda kv: -len(kv[1])):
        if len(g) < max(40, 0.01 * len(d)):
            continue
        cells = [route, f"{len(g) / len(d):.0%}", f"{(low_ & (d['long_route'] == route)).sum() / max(1, low_.sum()):.0%}",
                  f"{(high_ & (d['long_route'] == route)).sum() / max(1, high_.sum()):.0%}"]
        cells += [_cell(g[col].to_numpy(float), g["game"].to_numpy(), fmt) for col, fmt in TABLE_COLUMNS]
        lines.append("| " + " | ".join(cells) + " |")
    if (d["decision"] == 0).all():
        lines.append("\nGold against the rival jungler is not at the first camp: total gold is not read until "
                     "the minute. At 90 s, here, it is until 3:45 (the end of the first clear).")
    return lines + [""]


def _diff(a: pd.DataFrame, b: pd.DataFrame, col: str, times: int = 300) -> tuple[float, float, float]:
    """Mean of `col` in `a` minus in `b`, with the 90% interval resampling whole matches in each group."""
    def total(g):
        v = g[["game", col]].dropna().groupby("game")[col].agg(["sum", "count"])
        return v["sum"].to_numpy(), v["count"].to_numpy()
    sa, ca = total(a)
    sb, cb = total(b)
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(times):
        i, j = rng.integers(0, len(sa), len(sa)), rng.integers(0, len(sb), len(sb))
        diffs.append(sa[i].sum() / ca[i].sum() - sb[j].sum() / cb[j].sum())
    return float(sa.sum() / ca.sum() - sb.sum() / cb.sum()), float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95))


def state_table(d: pd.DataFrame) -> list[str]:
    """The same route in different states: ganking a lane according to where that lane's wave is, against continuing to
    clear in that same state (from the 3rd to the 6th camp, which is when the first gank is decided)."""
    d = d[d["decision"].between(3, 6)]
    lines = ["### Ganking or continuing to clear, according to where the wave is (from the 3rd to the 6th camp)\n",
              "Wave from 0 (stuck to their team's tower) to 1 (stuck to the rival's). **Rival ahead**: the "
              "wave is in their half (≤ 0.45), so the rivals of that lane play far from their tower. **With "
              "prio**: the wave is in the rival half (≥ 0.55). The difference is gank minus continuing to "
              "clear, in the same state.\n",
              "| lane | state | decisions | gank | gank − clear: WP at 90 s | WP at 5 min | he dies (90 s) | "
              "gold against the rival jungler (5 min) |", "|---|---|---|---|---|---|---|---|"]
    for lane in ("top", "mid", "bot"):
        wave, flash = d[f"{lane}_wave"], d[f"{lane}_no_flash_rival"].fillna(0)
        states = [("rival ahead", wave <= 0.45), ("with prio", wave >= 0.55),
                   ("rival ahead and without flash", (wave <= 0.45) & (flash >= 1))]
        for name, sel in states:
            s = d[sel]
            gank, cleared_at = s[s["long_route"] == f"gank {lane}"], s[s["route"] == "camp"]
            if len(gank) < 40:
                continue
            cells = [lane, name, f"{len(s):,d}", f"{len(gank) / len(s):.1%} ({len(gank)})"]
            cells += [_diff_cell(gank, cleared_at, col, fmt) for col, fmt in DIFF_COLUMNS]
            lines.append("| " + " | ".join(cells) + " |")
    return lines + [""]


DIFF_COLUMNS = [(f"centred_{WP_H[90]}", "{:+.2f}"), (f"centred_{WP_H[300]}", "{:+.2f}"), ("centred_dies_in_horizon", "{:+.1%}"),
                (f"centred_{GOLD_H[300]}", "{:+.0f}")]


def _diff_cell(a: pd.DataFrame, b: pd.DataFrame, col: str, fmt: str) -> str:
    if a[col].notna().sum() < 30 or b[col].notna().sum() < 30:
        return ""
    m, lo, hi = _diff(a, b, col)
    txt = fmt.format(m)
    return f"{'**' + txt + '**' if lo > 0 or hi < 0 else txt} [{fmt.format(lo)}, {fmt.format(hi)}]"


def counter_gank_table(d: pd.DataFrame) -> list[str]:
    """When the enemy jungler plants themselves in a lane in the 30 s following the decision (from the 2nd camp):
    whoever goes to that lane (counter-gank) against whoever does something else, in that same state."""
    d = d[d["decision"] >= 2]
    lines = ["### Counter-ganking or carrying on with their own, when the rival jungler is going to gank (from the 2nd camp)\n",
              "Decisions in which the rival jungler plants themselves in that lane, beside one of their own, "
              "within the next 30 s. **They saw it**: their team saw them in that lane in the 10 s before. "
              "The difference is counter-gank minus the other route, in the same state.\n",
              "| lane | decisions | they saw it | counter-gank (Master+) | counter-gank minus | WP at 90 s | "
              "WP at 5 min | he dies (90 s) | gold against the rival jungler (5 min) |", "|---|---|---|---|---|---|---|---|---|"]
    for lane in ("top", "mid", "bot"):
        s = d[d["rival_ganks"].fillna("") == lane]
        goes = s[s["long_route"] == f"contragank {lane}"]
        if len(goes) < 40:
            continue
        high_ = s[s["league_i"].isin(HIGH)]
        head = [lane, f"{len(s):,d}", f"{(s['rival_lane_seen'].fillna('') == lane).mean():.0%}",
               f"{len(goes) / len(s):.1%} ({(high_['long_route'] == f'contragank {lane}').mean():.1%})"]
        others_ = [("keep clearing", s["route"] == "camp"), ("invade", s["route"] == "invade"),
                 ("go back to base", s["route"] == "base"),
                 ("gank another lane", s["route"].isin(["gank", "counter_gank"]) & (s["detail"] != lane))]
        for name, sel in others_:
            another = s[sel]
            if len(another) < 40:
                continue
            lines.append("| " + " | ".join(head + [name] + [_diff_cell(goes, another, col, fmt) for col, fmt in DIFF_COLUMNS])
                          + " |")
            head = ["", "", "", ""]
    return lines + [""]


def _moment(decision) -> str:
    return "7+" if decision >= 7 else str(int(decision))


def _lane_state(wave: float) -> str:
    return "rival ahead" if wave <= 0.45 else "with prio" if wave >= 0.55 else ""


BASE_STATES = ("low health", "low gold and good health", "from 800 to 1,299 gold", "1,300 gold or more")


def _base_state(gold, health) -> str:
    """For going back to base: with less than half health, or with how much unspent gold if health is fine."""
    gold, health = pd.to_numeric(gold, errors="coerce"), pd.to_numeric(health, errors="coerce")
    if pd.isna(gold) or pd.isna(health):
        return ""
    if health < 0.5:
        return BASE_STATES[0]
    return BASE_STATES[1] if gold < 800 else BASE_STATES[2] if gold < 1300 else BASE_STATES[3]


def _rival_ganks(row) -> str:
    r = row.get("rival_ganks")
    return r if isinstance(r, str) else ""


# What is expected isn't calibrated in all states: with less than half health, what comes out exceeds what is expected by
# almost a WP point whatever they do (and a less regularised model doesn't fix it: it predicts worse out of fold).
# Since going back to base is chosen mostly at low health, comparing it with the moment's mean would mix it with that. So
# each residual is centred on its cell, the moment and the health and gold state: routes are compared with the other
# decisions of the same moment and the same state.
MIN_CELL = 200
PER_CELL = 150  # cases of a route in a cell finer than the moment to value it there (otherwise, the coarser one)
CENTRED =(*(WP_H[h] for h in HORIZONS), *DIES_H.values(), *GOLD_H.values())


def _base_states(df: pd.DataFrame) -> np.ndarray:
    return np.array([_base_state(o, v) for o, v in zip(df["gold_unspent"], df["health"])], dtype=object)


def centre(df: pd.DataFrame) -> pd.DataFrame:
    """Adds `cen_<outcome>`: the residual minus its cell's mean (the moment, 0-6 or 7+, and `_base_state`); cells
    with fewer than MIN_CELL decisions use their moment's mean."""
    df = df.copy()
    moment = df["decision"].map(_moment).to_numpy()
    cell = pd.Series([f"{m}|{e}" for m, e in zip(moment, _base_states(df))], index=df.index)
    small_ = cell.map(cell.value_counts()) < MIN_CELL
    cell[small_] = [f"{m}|" for m in moment[small_.to_numpy()]]
    for col in CENTRED:
        r = df[f"res_{col}"]
        df[f"centred_{col}"] = r - r.groupby(cell).transform("mean")
    return df


def _keys(decision: int, eb: str, rival: str) -> list[tuple[str, str, str]]:
    """The cells in which a decision is compared, from the finest to the coarsest: the moment; from the 3rd
    camp, whether the enemy jungler is going to gank and where; from the 7th, also the health and gold."""
    m = _moment(decision)
    if decision >= 7:
        return [(m, eb, rival), (m, eb, "*"), (m, "*", rival), (m, "*", "*")]
    if decision >= 3:
        return [(m, "*", rival), (m, "*", "*")]
    return [(m, "*", "*")]


def _value(t: pd.DataFrame, means: dict, columns: list[str]) -> dict:
    v = {"wp": {}, "it": {}, "hi": {}, "n": len(t),
         "died": float(t["centred_dies_in_horizon"].mean() - means["centred_dies_in_horizon"])}
    for hz, col in zip(HORIZONS, columns):
        x = t[col].to_numpy(float) - means[col]
        ok = ~np.isnan(x)
        if ok.sum() < 30:
            continue
        v["it"][hz], v["hi"][hz] = _ci(x[ok], t["game"].to_numpy()[ok], times=200)
        v["wp"][hz] = float(x[ok].mean())
    return v


def values(df: pd.DataFrame) -> dict:
    """What each route is worth in each cell (`_keys`), against the average decision of that cell, with its interval: the
    WP at each horizon and the risk of dying in 90 s. And the ganks from the 3rd camp on, according to where that lane's
    wave is (against the average decision with the wave like that). It is what `game` shows: a route's
    state-by-state value can't yet be learned with 5,000 matches (see the report), so that of the
    finest cell with at least PER_CELL cases of that route is used (40 in the moment's)."""
    d = df.copy()
    d["m"] = d["decision"].map(_moment)
    d["eb"] = _base_states(d)
    d["rg"] = d["rival_ganks"].fillna("").astype(object).astype(str)
    columns = [f"centred_{WP_H[h]}" for h in HORIZONS]
    out = {}
    levels = [(("m",), lambda x: x), (("m", "rg"), lambda x: x[x["decision"] >= 3]),
               (("m", "eb"), lambda x: x[x["decision"] >= 7]), (("m", "eb", "rg"), lambda x: x[x["decision"] >= 7])]
    for dims, filter_ in levels:
        minimum = 40 if dims == ("m",) else PER_CELL
        for key, g in filter_(d).groupby(list(dims)):
            key = dict(zip(dims, key if isinstance(key, tuple) else (key,)))
            cell = (key["m"], key.get("eb", "*"), key.get("rg", "*"))
            means = {c: g[c].mean() for c in (*columns, "centred_dies_in_horizon")}
            for route, t in g.groupby("long_route"):
                if len(t) >= minimum:
                    out[(cell, route)] = _value(t, means, columns)
    d["group"] = np.where(d["decision"] >= 7, "7+", "3-6")
    for group, g in d[d["decision"] >= 3].groupby("group"):
        for lane in ("top", "mid", "bot"):
            state = g[f"{lane}_wave"].map(_lane_state)
            for e in ("rival ahead", "with prio"):
                s = g[state == e]
                t = s[s["long_route"] == f"gank {lane}"]
                if len(t) >= 40:
                    means = {c: s[c].mean() for c in (*columns, "centred_dies_in_horizon")}
                    out[(("wave", group, e), f"gank {lane}")] = _value(t, means, columns)
    return out


def base_table(d: pd.DataFrame) -> list[str]:
    """Going back to base against continuing to clear, at each horizon: what it loses right away and what it recovers later. By
    moment and, from the 7th camp on, according to unspent gold and health (before, going back after the 3rd
    camp is its own thing: it is done with little gold on purpose)."""
    cols = [(f"centred_{WP_H[h]}", "{:+.2f}") for h in HORIZONS] + [("centred_dies_in_horizon", "{:+.1%}"),
                                                                   (f"centred_{GOLD_H[90]}", "{:+.0f}"),
                                                                   (f"centred_{GOLD_H[300]}", "{:+.0f}")]
    lines = ["### Going back to base or continuing to clear, at each horizon\n",
              "Going back to base minus continuing to clear, in the same state (the residual over what is expected for each).\n",
              "| when | state | go back | " + " | ".join(f"WP a {NAME_H[h]}" for h in HORIZONS)
              + " | he dies (90 s) | gold against the rival jungler (90 s) | (5 min) |", "|---|---|---|---|---|---|---|---|---|"]
    chunks = [(title, "everyone", d[filter_(d)]) for title, filter_ in MOMENTS[3:]]
    g = d[d["decision"] >= 7]
    gold, health = pd.to_numeric(g["gold_unspent"], errors="coerce"), pd.to_numeric(g["health"], errors="coerce")
    for name, sel in (("less than 800 gold", gold < 800), ("from 800 to 1,299 gold", gold.between(800, 1299)),
                        ("from 1,300 to 1,999 gold", gold.between(1300, 1999)), ("2,000 gold or more", gold >= 2000),
                        ("less than half health", health < 0.5),
                        ("less than half health and less than 800 gold", (health < 0.5) & (gold < 800)),
                        ("half health or more and less than 800 gold", (health >= 0.5) & (gold < 800))):
        chunks.append(("from the 7th", name, g[sel]))
    for when, state, s in chunks:
        b, c = s[s["route"] == "base"], s[s["route"] == "camp"]
        if len(b) < 40 or len(c) < 40:
            continue
        lines.append(f"| {when} | {state} | {len(b) / len(s):.0%} | "
                      + " | ".join(_diff_cell(b, c, col, fmt) for col, fmt in cols) + " |")
    return lines + [""]


def report(df: pd.DataFrame) -> None:
    print("## What they choose and how much it yields, at each moment\n")
    print("WP in neutral WP points (a kill is about 4.7) against the decisions of the same moment with the "
          "same health and gold state (less than half health; or, with half health or more, less than 800, "
          "800 to 1,299 or 1,300 or more unspent gold); in brackets, the 90% interval; in bold, what does not "
          "cross zero.\n")
    for title, filter_ in MOMENTS:
        print("\n".join(moment_table(df[filter_(df)], title)), flush=True)
    print("## Going back to base\n")
    print("\n".join(base_table(df)), flush=True)
    print("## The state changes the value of the route\n")
    print("\n".join(state_table(df)), flush=True)
    print("\n".join(counter_gank_table(df)), flush=True)


def analyse(output: Path, npz: Path, model_json: Path) -> None:
    from sklearn.model_selection import GroupKFold

    df = pd.read_csv(output / "decisions.csv.gz", low_memory=False)
    df = with_value(df, wp(npz, model_json))
    df["long_route"] = long_route(df)
    X, categories = features(df)
    df["league_i"], df["level"] = X["league_i"], X["level"]
    g = df["game"].to_numpy()
    print(f"# Jungler routes\n\n{len(df):,d} decisions from {df['game'].nunique():,d} games "
          f"({df[df['value_90'].notna()]['game'].nunique():,d} with the per-second WP).\n")
    for col in OUTCOMES:
        y = pd.to_numeric(df[col], errors="coerce").to_numpy(float)
        exp_ = _expected(X, y, g, binary=(col in BINARY))
        df[f"expected_{col}"], df[f"res_{col}"] = exp_, y - exp_
        ok = ~np.isnan(y) & ~np.isnan(exp_)
        r2 = 1 - np.mean((y[ok] - exp_[ok]) ** 2) / np.var(y[ok])
        print(f"- what is expected of `{col}` without the route: out-of-fold R² {r2:.3f} ({ok.sum():,d} decisions)", flush=True)
    print()
    df = centre(df)
    report(df)

    # the models for `game`: the high league's policy and each route's value in each state
    routes = df["long_route"].value_counts()
    routes = list(routes[routes >= 200].index)
    used = df["long_route"].isin(routes).to_numpy()
    Xr = X.copy()
    Xr["route_i"] = df["long_route"].map({r: i for i, r in enumerate(routes)})
    policy = _policy(X).fit(X[used & df["league_i"].isin(HIGH).to_numpy()],
                                    Xr.loc[used & df["league_i"].isin(HIGH).to_numpy(), "route_i"].astype(int))
    # does the route say anything about what happens? the same model with and without the route, out of fold, at each horizon
    print("\n## Does the route contribute?\n\n| horizon | R² without the route | R² with the route |\n|---|---|---|")
    for h in HORIZONS:
        y = df[WP_H[h]].to_numpy(float)
        ok = used & ~np.isnan(y)
        q = _regressor(X, extra=[True])
        without, with_ = np.full(len(y), np.nan), np.full(len(y), np.nan)
        idx = np.flatnonzero(ok)
        for tr, te in GroupKFold(FOLDS).split(idx, groups=g[idx]):
            a, b = idx[tr], idx[te]
            without[b] = _regressor(X).fit(X.iloc[a], y[a]).predict(X.iloc[b])
            with_[b] = q.fit(Xr.iloc[a], y[a]).predict(Xr.iloc[b])
        v = np.var(y[ok])
        print(f"| {NAME_H[h]} | {1 - np.mean((y[ok] - without[ok]) ** 2) / v:.4f} | "
              f"{1 - np.mean((y[ok] - with_[ok]) ** 2) / v:.4f} |", flush=True)
    print()
    # the policy, out of fold: does it predict what the high league does better than each route's frequency at its moment?
    high_ = np.flatnonzero(used & df["league_i"].isin(HIGH).to_numpy())
    yr = Xr["route_i"].to_numpy()
    moment = np.minimum(df["decision"].to_numpy(), 7)
    P, B = np.zeros((len(high_), len(routes))), np.zeros((len(high_), len(routes)))
    for tr, te in GroupKFold(FOLDS).split(high_, groups=g[high_]):
        mm = _policy(X).fit(X.iloc[high_[tr]], yr[high_[tr]].astype(int))
        P[np.ix_(te, mm.classes_.astype(int))] = mm.predict_proba(X.iloc[high_[te]])
        tab = pd.crosstab(moment[high_[tr]], yr[high_[tr]], normalize="index").reindex(columns=range(len(routes)),
                                                                                       fill_value=0)
        B[te] = tab.reindex(moment[high_[te]]).to_numpy()
    yy = yr[high_].astype(int)
    k = np.arange(len(yy))
    print(f"High-league policy, out of fold: log-loss {-np.mean(np.log(np.clip(P[k, yy], 1e-4, 1))):.3f} "
          f"against {-np.mean(np.log(np.clip(B[k, yy], 1e-4, 1))):.3f} of the frequency per moment; the most probable route "
          f"is right {np.mean(P.argmax(1) == yy):.1%} of the time (the frequency, {np.mean(B.argmax(1) == yy):.1%}).\n")
    (output / "routes_model.pkl").write_bytes(pickle.dumps({"policy": policy, "routes": routes,
                                                             "categories": categories, "columns": list(X.columns),
                                                             "values": values(df)}))
    df.drop(columns=[c for c in df.columns if c.startswith("expected_")]).to_pickle(output / "valued_decisions.pkl")


def _value_of(vals: dict, decision: int, route: str, row: pd.Series) -> dict | None:
    """A route's value for this decision: that of the finest cell that has that route (`_keys`). Ganks,
    when the enemy jungler isn't going to gank, according to that lane's wave if it is clearly on one side."""
    rival = _rival_ganks(row)
    if route.startswith("gank ") and decision >= 3 and not rival:
        state = _lane_state(row.get(f"{route.split(' ')[1]}_wave", 0.5))
        key = (("wave", "7+" if decision >= 7 else "3-6", state), route)
        if state and key in vals:
            return vals[key] | {"state": state}
    for cell in _keys(decision, _base_state(row.get("gold_unspent"), row.get("health")), rival):
        if (cell, route) in vals:
            return vals[(cell, route)]
    return None


def _comma(x: float, fmt: str = "{:+.1f}") -> str:
    return fmt.format(x).replace("-", "−")


def _txt(v: dict | None) -> str:
    """WP at 90 s / 3 min / 5 min (≈ if the interval crosses zero), the risk of dying and the split."""
    if v is None:
        return "no data"
    wps = []
    for h in HORIZONS:
        if h not in v["wp"]:
            wps.append("?")
            continue
        clear = v["it"][h] > 0 or v["hi"][h] < 0
        wps.append(("" if clear else "≈") + _comma(v["wp"][h]))
    return " / ".join(wps) + f"; dies {_comma(100 * v['died'], '{:+.0f}')}%" + \
        (f"; {v['state']}" if v.get("state") else "")


def game(output: Path, pid: str, champion: str, file: str | None = None) -> None:
    """A jungler's tree in a match, decision by decision (with the `routes.py rows` rows of that match):
    what Master-and-above junglers choose in that state and what each route is worth."""
    m = pickle.loads((output / "routes_model.pkl").read_bytes())
    file_path = Path(file) if file else output / "games" / f"{pid}.csv.gz"
    df = pd.read_csv(file_path, low_memory=False)
    df = df[df["jungler"] == champion].sort_values("t").reset_index(drop=True)
    df["long_route"] = long_route(df)
    X, _ = features(df, m["categories"])
    X = X.reindex(columns=m["columns"])
    routes, vals = m["routes"], m["values"]
    pol = np.zeros((len(X), len(routes)))
    for league in HIGH:  # the high-league policy: the mean with the league set to Master, GM and Challenger
        Xl = X.copy()
        Xl["league_i"] = league
        pol[:, m["policy"].classes_.astype(int)] += m["policy"].predict_proba(Xl) / len(HIGH)
    print(f"## {champion} · {pid}\n")
    print("In each decision, the routes that at least 5% of Master-and-above junglers choose in that state, "
          "with the share that chooses it and what it is worth against the other decisions in the same state: "
          "WP points at 90 s, 3 min and 5 min (≈ if the interval crosses zero) and the risk of dying within "
          "90 s. The state is the moment; from the 3rd camp, also whether the rival jungler is going to gank "
          "and where; from the 7th, also the health and the unspent gold. The ganks, if the rival is not "
          "going to gank, according to the wave of that lane.\n")
    for i, f in df.iterrows():
        possible = sorted(((pol[i, k], r) for k, r in enumerate(routes) if pol[i, k] >= MINIMUM), reverse=True)
        if not possible:
            continue
        did = f["long_route"]
        k_did = routes.index(did) if did in routes else None
        level = int(f["level"]) if pd.notna(f["level"]) else 1
        health = f"{float(f['health']):.0%}" if pd.notna(f["health"]) else "?"
        head = f"**{_clock(f['t'])}** · after {f['after']} · level {level} · health {health} · {int(f['gold_unspent'])} gold"
        rival = f.get("rival_ganks")
        if isinstance(rival, str) and rival:
            sighted = " (they saw it)" if f.get("rival_lane_seen") == rival else ""
            head += f" · the rival jungler is going to gank {rival}{sighted}"
        options = " · ".join(f"{r} {p:.0%} ({_txt(_value_of(vals, int(f['decision']), r, f))})"
                              for p, r in possible)
        choose = f"; {pol[i, k_did]:.0%} choose it" if k_did is not None else ""
        print(f"- {head}. High league: {options}. **Did: {did}** ({_txt(_value_of(vals, int(f['decision']), did, f))}{choose}).")
