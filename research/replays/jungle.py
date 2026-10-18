"""What a reference jungle coach teaches, measured in the match (the Qiyana review, EUW1_8008878706, 2026-10-10).

The moments that come out of here are the usual `kind`s (`ward`, `camps`, `play`, `fog`, `back`, `opening`) and don't score (`no_score`) until they are calibrated
with more reviews. The importance the coach gives (HIGH, MEDIUM, LOW) is severity 3, 2 and 1.

- the level 1 ward: the eight spots that matter (four per side) and their name;
- the first clear: the camp it starts with, the recall after the third and what time it ends (the crab spawns at 2:55);
- the first crab, with the information they had on the enemy jungler;
- the information you give: walking through the view of an enemy ward you already knew was there;
- the recall windows (gold, your teammates' tempo and the objective timers) and the cancelled recalls;
- the jungler's advantage (levels, gold in items and how many lanes are ahead) and what changes with it: opening to camps with an
  objective in play, or farming your own while the enemy jungler is dead;
- the pet's upgraded smite;
- the net result of a play: the bad that falls inside a play that paid off isn't counted separately.
"""

from __future__ import annotations

import collections
import math

import coach as C
import moments as M

IMPORTANCE = {"HIGH": 3, "MEDIA": 2, "LOW": 1}

# The jungler's level 1 ward: (name, type, x, z) per team. «Defensive» covers an entrance to your jungle; «offensive» tracks the enemy jungler's pathing.
SPOTS_WARD_1 = {
    "200": [("Raptors entrance", "defensive", 6430.0, 8625.0), ("Bot river banana bush", "defensive", 10073.0, 6027.0),
            ("Enemy Raptors", "offensive", 7688.0, 4982.0), ("Enemy Blue", "offensive", 4110.0, 7939.0)],
    "100": [("Raptors entrance", "defensive", 8586.0, 6142.0), ("Top river banana bush", "defensive", 4944.0, 8559.0),
            ("Enemy Raptors", "offensive", 7181.0, 9899.0), ("Enemy Blue", "offensive", 10808.0, 7138.0)],
}
SPOT_RADIUS = 800.0  # ponytail: by eye; the defensive ones fall inside named bushes and the offensive ones aren't in any
SAFE_CRAB = 12.0  # seconds the enemy jungler takes to reach the crab for contesting it to carry no risk
CRAB_SPAWN = 175.0  # the first crab spawns at 2:55: the first clear has to have finished
CLEAR_IDEAL = 170.0  # and at 2:50 with a single smite spent
RECALL_GOLD = 1300.0  # with that much on them there is enough for a whole item: it is the window to go back
LATE_RECALL = 30.0  # seconds with that gold on them, staying on the map, from which it is already going back late
SYNC = 20.0  # seconds on each side in which a teammate going back to base is going back at the same time
LEVEL_ADVANTAGE = 1  # a level of difference with the enemy jungler is already an advantage for snowballing
ITEMS_ADVANTAGE = 600.0  # gold in items they have over the enemy jungler (a component and a bit more)
ITEMS_WITH_LANES = 300.0  # and with three lanes ahead, half
WARD_REACH = M.RANGE["ward"]
KNOWS = 1100.0  # a control ward of yours within this of an enemy ward shows it: you know it
BIG = {"Blue", "Red", "Gromp", "Krugs", "Raptors", "Wolves"}  # the large monsters of each camp: they feed the jungle item's pet
EVOLUTION = 15  # charges for the first evolution (Unleashed Smite)
ITEMS = {1036: "a Long Sword", 1037: "a Pickaxe", 1001: "Boots", 3134: "a Serrated Dirk", 2055: "a Control Ward"}


def _side(p: C.Game) -> str:
    return "blue" if p.team == "100" else "red"


def _row(p: C.Game, champion: str | None, t: float) -> dict | None:
    return C._row(p.table.get(champion or "", {}), t)


def _gold(p: C.Game, t: float) -> float:
    return C._num(_row(p, p.champion, t), "gold")


def _recalls(p: C.Game) -> list[dict]:
    if not hasattr(p, "_recalls_"):
        p._recalls_ = M.recalls(p.events, p.rows)
    return p._recalls_


def _mine(p: C.Game) -> list[dict]:
    return [c for c in p.events["camps"] if c.get("killer") == p.me["net_id"]]


# ── The objectives and the advantage ──────────────────────────────────────────────────────────────────────

def objectives(p: C.Game) -> list[dict]:
    """The objectives that count for a recall's timer: when they spawn and when they fall (dragons, Voidgrubs, Herald and Baron)."""
    if hasattr(p, "_objectives_"):
        return p._objectives_
    falls: dict[str, list[float]] = collections.defaultdict(list)
    for c in p.events["camps"]:
        name = c["camp"].split(" (")[0]
        falls[name].append(c["time"])
    out, seen = [], set()
    for e in p.events["events"]:
        if e["type"] != "SpawnNeutral":
            continue
        c = (e.get("character") or "").lower()
        name = ("Dragon" if c.startswith("sru_dragon") else "Voidgrub" if c == "sru_horde" else "Herald" if c == "sru_riftherald"
                  else "Baron" if c == "sru_baron" else None)
        if name is None or (name, round(e["time"])) in seen:
            continue
        seen.add((name, round(e["time"])))
        after = sorted(t for t in falls[name] if t >= e["time"])
        falls_ = (after[2] if len(after) >= 3 else math.inf) if name == "Voidgrub" else (after[0] if after else math.inf)
        out.append({"name": name, "text": {"Voidgrub": "the Voidgrubs", "Herald": "the Rift Herald", "Baron": "Baron Nashor",
                                                   "Dragon": "the Dragon"}[name], "leaves": e["time"], "falls": falls_,
                      "spot": tuple(e["position"])})
    p._objectives_ = sorted(out, key=lambda o: o["leaves"])
    return p._objectives_


def in_play(p: C.Game, t: float, before: float = 60.0) -> dict | None:
    """The objective already in play at that second or spawning in the next `before`, with the seconds remaining (negative if it already spawned)."""
    alive = [o for o in objectives(p) if o["leaves"] - t <= before and o["falls"] > t]
    if not alive:
        return None
    o = min(alive, key=lambda o: o["leaves"])
    return o | {"missing": o["leaves"] - t}


def advantage(p: C.Game, t: float) -> dict:
    """The advantage with which the jungler plays at that second: levels and gold in items against the enemy jungler (what counts for snowballing,
    more than the gold they carry), and how many of the four laners are ahead of their lane opponent."""
    me, opp = _row(p, p.champion, t), _row(p, p.rival, t)
    if not me or not opp:
        return {"ahead": False, "level": 0, "items": 0.0, "lines": 0}
    level = int(C._num(me, "level") - C._num(opp, "level"))
    items_ = M._spent_gold(me) - M._spent_gold(opp)
    lines = 0
    for position in ("TOP", "MIDDLE", "BOTTOM", "UTILITY"):
        a, b = _row(p, C._of(p, p.team, position), t), _row(p, C._of(p, p.rival_team, position), t)
        if a and b and (C._num(a, "level") - C._num(b, "level") >= 1 or C._num(a, "total_gold") - C._num(b, "total_gold") >= 400):
            lines += 1
    # a level of difference, or the gold in items, or three lanes that are winning (those that can move the map) with some item advantage
    ahead = level >= LEVEL_ADVANTAGE or items_ >= ITEMS_ADVANTAGE or (lines >= 3 and items_ >= ITEMS_WITH_LANES)
    return {"ahead": ahead, "level": level, "items": items_, "lines": lines}


def _advantage_txt(v: dict) -> str:
    parts = []
    if v["level"]:
        parts.append(f"{v['level']:+d} level{'s' if abs(v['level']) > 1 else ''}")
    parts.append(f"{v['items']:+,.0f} g in items against their jungler")
    return f"you were {'ahead' if v['ahead'] else 'not ahead'} ({', '.join(parts)}; {v['lines']} of your 4 laners ahead of their opponent)"


def _arrival(p: C.Game, champion: str, t: float, spot: tuple[float, float]) -> float | None:
    """The seconds that champion takes to reach that place in a straight line at their movement speed."""
    f = _row(p, champion, t)
    if not f or not f["x"]:
        return None
    return math.dist((float(f["x"]), float(f["z"])), spot) / max(300.0, C._num(f, "move_speed") or 345.0)


# ── The level 1 ward ──────────────────────────────────────────────────────────────────────────────────────

def level_1_ward(p: C.Game, mine: tuple[float, tuple[float, float]] | None) -> list[dict]:
    """The jungler's level 1 ward against the eight spots that matter: in one of them, good; elsewhere, neutral; no ward, bad."""
    if mine is None:
        return [C._moment(p, 60, None, "ward", "bad", IMPORTANCE["HIGH"], "No level-1 ward",
                           "You didn't put a ward in the first two minutes. A jungler plays through information: with the level-1 ward "
                           "you always want some, defensive (an entrance to your jungle) or offensive (tracking their jungler's pathing).")]
    t, spot = mine
    spots = SPOTS_WARD_1[p.team]
    name, kind, x, z = min(spots, key=lambda s: math.dist(spot, (s[2], s[3])))
    where = p.place(spot)
    if math.dist(spot, (x, z)) <= SPOT_RADIUS:
        reason = ("it covers an entrance to your jungle" if kind == "defensive" else "it reads where their jungler starts and paths")
        text = (f"You put the level-1 ward at {C._clock(t)} in {where}: the {name} spot ({kind}), {reason}. A jungler plays through "
                 "information: with the level-1 ward you always want some, defensive (an entrance to your jungle) or offensive (tracking "
                 "their jungler's pathing). If the offensive one is too risky, the defensive one is the answer.")
        return [C._moment(p, t, spot, "ward", "good", IMPORTANCE["HIGH"], f"Level-1 ward: {name}", text, spot=name, spot_type=kind)]
    key = "; ".join(f"{n} ({k})" for n, k, _x, _z in spots)
    text = (f"You put the level-1 ward at {C._clock(t)} in {where}, which is not one of the key spots on your side: {key}. "
             "It isn't a mistake, but those are the ones that give a jungler information from the first minute.")
    return [C._moment(p, t, spot, "ward", "neutral", IMPORTANCE["LOW"], "Level-1 ward outside the key spots", text)]


# ── The first clear ───────────────────────────────────────────────────────────────────────────────────────

def _first_clear(p: C.Game) -> list[tuple[float, str]]:
    """Their camps of the first clear, in order: up to the first that repeats."""
    own_items = sorted((c["time"], c["camp"]) for c in _mine(p)
                   if c.get("side") == _side(p) and c["camp"] in (*C.CAMPS, "Blue", "Red") and c["time"] <= 240)
    out: list[tuple[float, str]] = []
    for t, camp in own_items:
        if camp in [c for _t, c in out]:
            break
        out.append((t, camp))
    return out


def first_clear(p: C.Game) -> list[dict]:
    """The camp it starts with, the recall after the third and what time the clear ends, with the smite and the spells."""
    if p.position != "JUNGLE":
        return []
    clear = _first_clear(p)
    if len(clear) < 3:
        return []
    out = []
    order = " → ".join(c for _t, c in clear)
    first = clear[0][1]
    if first == "Raptors":
        out.append(C._moment(p, clear[0][0], p.where(p.champion, clear[0][0]), "camps", "good", IMPORTANCE["MEDIA"], "Started Raptors",
                                f"You started with your Raptors and cleared {order}. Starting Raptors is right as long as your bot camps aren't at "
                                "risk and you are back at Raptors when their timer hits 0. If you wanted to spend time in a lane, starting at a "
                                "buff would be better: you don't have such an early timer to get back to."))
    # the recall after the third camp
    third = clear[2][0]
    r = next((r for r in _recalls(p) if r["champion"] == p.champion and not r["cancelled"] and third <= r["time"] <= third + 25), None)
    if r:
        purchases = [e["item_id"] for e in p.events["events"] if e["type"] == "BuyItem" and e["net_id"] == p.me["net_id"]
                   and r["time"] <= e["time"] <= r["time"] + 40]
        what = _item_list(purchases)
        out.append(C._moment(p, r["time"], p.where(p.champion, r["time"]), "back", "good", IMPORTANCE["LOW"], "Recalled after the third camp",
                                f"You cleared {' → '.join(c for _t, c in clear[:3])} and recalled at {C._clock(r['time'])} with {_gold(p, r['time']):,.0f} g"
                                + (f", buying {what}" if what else "")
                                + ". That gives you a recall window at the end of the first half of the path and lets you play the map with the "
                                  "item bought (a stat lead); the rest of the clear should still get you to the first Scuttle (2:55)."))
    # what time the whole clear ends
    if len(clear) >= 6:
        end = clear[-1][0]
        smites = [e["time"] for e in p.events["events"] if e["type"] == "CastSpell" and e["net_id"] == p.me["net_id"]
                  and e["spell"] == "SummonerSmite" and e["time"] <= end + 1]
        f = _row(p, p.champion, end + 1)
        fallen = [s.upper() for s in "qwe" if f and f.get(f"{s}_ready") == "False"]
        last_ = clear[-1][1]
        late = end > CRAB_SPAWN
        if late or end > CLEAR_IDEAL:
            text = (f"Your first clear ended at {C._clock(end)} ({last_}): {C._duration(end - CLEAR_IDEAL)} after the {C._clock(CLEAR_IDEAL)} a clean one reaches"
                     f"{' and ' + C._duration(end - CRAB_SPAWN) + ' after the first Scuttle spawns (' + C._clock(CRAB_SPAWN) + ')' if late else ''}. "
                     f"You had spent {len(smites)} Smite{'s' if len(smites) != 1 else ''} ({C._list([C._clock(s) for s in smites])})"
                     + (f" and {C._list(fallen)} {'was' if len(fallen) == 1 else 'were'} on cooldown" if fallen else "") + ". "
                     "If something happens at the Scuttle you arrive late and without them: a second of difference is the one that lets you "
                     "arrive and win the fight or the camp. The target is to finish before 2:50 spending a single Smite (you have two charges: "
                     "one for the first buff and the second one kept for the Scuttle). Some champions can't clear that fast; it is still the target.")
            out.append(C._moment(p, end, p.where(p.champion, end), "camps", "bad" if late else "neutral",
                                    IMPORTANCE["HIGH"] if late and (len(smites) >= 2 or len(fallen) >= 2) else IMPORTANCE["MEDIA"] if late else IMPORTANCE["LOW"],
                                    "First clear finished late" if late else "First clear a little slow", text,
                                    clear_end=round(end, 1), smites=len(smites), spells_down=fallen))
        else:
            out.append(C._moment(p, end, p.where(p.champion, end), "camps", "good", IMPORTANCE["LOW"], "First clear on time",
                                    f"Your first clear ended at {C._clock(end)} ({last_}), before {C._clock(CLEAR_IDEAL)}, with {len(smites)} "
                                    f"Smite{'s' if len(smites) != 1 else ''} spent: you reach the first Scuttle with your spells and your Smite."))
    return out


def _item_list(ids: list[int]) -> str:
    return C._list(list(dict.fromkeys(ITEMS[i] for i in ids if i in ITEMS)))


# ── The first crab ────────────────────────────────────────────────────────────────────────────────────────

def crab(p: C.Game) -> list[dict]:
    """The first river crab they take, and whether they do it with information: where the enemy jungler was and what they had just cleared."""
    if p.position != "JUNGLE":
        return []
    kill = next((c for c in sorted(_mine(p), key=lambda c: c["time"]) if c["camp"] == "Scuttle" and c["time"] <= 420), None)
    if not kill or not p.rival:
        return []
    t, spot = kill["time"], tuple(kill["position"])
    f = _row(p, p.rival, t)
    if not f or not f["x"] or f["alive"] != "True":
        return []
    arrives = _arrival(p, p.rival, t, spot)
    far = math.dist((float(f["x"]), float(f["z"])), spot)
    own = p.team_of.get(p.rival)
    rival_net = next(j["net_id"] for j in p.events["players"] if j["champion"] == p.rival)
    latest = [(c["time"], c["camp"]) for c in p.events["camps"] if c.get("killer") == rival_net and t - 60 <= c["time"] <= t
               and c["camp"] in (*C.CAMPS, "Blue", "Red")][-3:]
    sighted = C._seen_ago(p, p.rival, t, 40)
    you_know = "you had him in sight" if sighted is not None and sighted < 3 else (f"you had seen him {sighted:.0f} s before" if sighted is not None else
                                                                            "nobody had seen him in the last 40 s, but you could read his clear")
    camps = C._list([f"{c} {C._clock(tt)}" for tt, c in latest]) or "nothing yet"
    safe = arrives is not None and arrives >= SAFE_CRAB
    text = (f"At {C._clock(t)} you took the {kill.get('side', '')} Scuttle in {p.place(spot)}. Their jungler ({p.rival}) was "
             f"{far:,.0f} units away, {arrives:.0f} s at his speed, in {p.place((float(f['x']), float(f['z'])))}; his last camps: {camps}; {you_know}. ")
    if safe:
        text += ("With that information there was no risk, so contesting the Scuttle is right. When you don't know where their jungler is and your "
                  "lanes can't move (their wave in a good state against yours in a bad one), don't.")
    else:
        text += (f"He could get there in about {arrives:.0f} s: contesting it was a risk. Do it with information on their jungler and with your "
                  "lanes able to move.")
    return [C._moment(p, t, spot, "play", "good" if safe else "neutral", IMPORTANCE["HIGH"] if safe else IMPORTANCE["LOW"],
                       "Contested the Scuttle with information" if safe else "Contested the Scuttle with their jungler close", text)]


# ── The information you give ──────────────────────────────────────────────────────────────────────────────

def _wards(p: C.Game) -> list[dict]:
    """Each ward in the match: when it spawns, when it dies, where, from which team and which item placed it."""
    owner_of = {j["net_id"]: j for j in p.events["players"]}
    cast = collections.defaultdict(list)
    for e in p.events["events"]:
        if e["type"] == "CastSpell" and e["spell"] in M.WARDS:
            cast[round(e["time"], 3)].append((e["net_id"], tuple(e["target"][:2]), e["spell"]))
    died = {e["net_id"]: e["time"] for e in p.events["events"] if e["type"] == "UnitDeath"}
    out = []
    for e in p.events["events"]:
        if e["type"] == "SpawnMinion" and e.get("character") in M.WARD_UNITS:
            if own_items := cast.get(round(e["time"], 3)):
                net, where, spell = own_items.pop(0)
                out.append({"t0": e["time"], "t1": died.get(e["net_id"], math.inf), "spot": where, "team": owner_of[net]["team"],
                              "champion": owner_of[net]["champion"], "control": spell == "JammerDevice"})
    return out


def info_you_give(p: C.Game) -> list[dict]:
    """The stretches in which the enemy team sees them thanks to a ward of theirs that they already knew was there (shown by a control ward of theirs right beside it):
    walking over it gives all the enemy laners where they are."""
    if p.position != "JUNGLE":
        return []
    wards = _wards(p)
    rivals = [w for w in wards if w["team"] == p.rival_team]
    controls = [w for w in wards if w["team"] == p.team and w["control"]]
    seconds = []
    for s in range(60, int(C.LANING_PHASE)):
        f = _row(p, p.champion, s)
        if not f or not f["x"] or f["alive"] != "True" or f.get("seen") != "True":
            continue
        me = (float(f["x"]), float(f["z"]))
        for w in rivals:
            if not (w["t0"] <= s <= w["t1"] and math.dist(me, w["spot"]) <= WARD_REACH):
                continue
            if any(g["alive"] == "True" and g["x"] and math.dist(me, (float(g["x"]), float(g["z"]))) <= M.RANGE["champion"]
                   for c in p.events["players"] if c["team"] == p.rival_team and (g := _row(p, c["champion"], s))):
                continue  # a champion sees it, not the ward
            # you know it from the time a control ward of yours, right beside it, coincides with it in time: it shows it (even if it is later killed)
            m = next((m for m in controls if math.dist(m["spot"], w["spot"]) <= KNOWS and max(m["t0"], w["t0"]) <= s
                      and m["t0"] <= w["t1"] and w["t0"] <= m["t1"]), None)
            if m:
                seconds.append((s, w | {"known": m["t0"]}))
                break
    out = []
    for group in C._streaks([{"t": s, "w": w} for s, w in seconds], gap=4.0):
        a, b, w = group[0]["t"], group[-1]["t"], group[0]["w"]
        where = C.place(*w["spot"], p.team)
        text = (f"At {C._clock(a)} you walked into the sight of a ward {w['champion']} had put at {C._clock(w['t0'])} in {where}, and their team saw you "
                 f"for {b - a + 1} s. You knew it was there: the control ward you put next to it at {C._clock(w["known"])} showed it to you. Now every lane adapts to where you are: their top laner can "
                 "play aggressive knowing you won't gank him, their bot lane knows they have to respect the next minute because you are on their side, "
                 "and their mid laner knows that if you gank him it is from the bot river. Go around it, even if it takes a few seconds more: giving "
                 "the enemy information is the basis of decision making.")
        out.append(C._moment(p, a, p.where(p.champion, a), "fog", "bad", IMPORTANCE["HIGH"], "Walked over a ward you knew about", text,
                                end=float(b)))
    return out


# ── The recall windows ────────────────────────────────────────────────────────────────────────────────────

def _stretches_with_gold(p: C.Game) -> dict[int, int]:
    """Second → when `RECALL_GOLD` was crossed while outside the base (the same stretch, without going back to base or dying)."""
    base = p.bases[p.team]
    out, ts = {}, None
    for s in range(60, int(p.events["game_length"])):
        f = _row(p, p.champion, s)
        if not f or not f["x"]:
            continue
        if f["alive"] != "True" or math.dist((float(f["x"]), float(f["z"])), base) < 2000:
            ts = None
            continue
        if C._num(f, "gold") >= RECALL_GOLD:
            ts = ts if ts is not None else s
            out[s] = ts
        else:
            ts = None
    return out


def recall_windows(p: C.Game) -> list[dict]:
    """Each of the jungler's recalls with gold to spare and how long they took to go back from having it: the recall window is set by the gold, the
    teammates' tempo (everyone opening the map at once) and the objective timers; going back late with all three in place is losing it."""
    if p.position != "JUNGLE":
        return []
    mine_list = [r for r in _recalls(p) if r["champion"] == p.champion and r["time"] > 120]
    spans = _stretches_with_gold(p)
    out = []
    worst = 0
    for r in mine_list:
        tr = r["time"]
        if r["cancelled"]:
            continue
        worst = 0
        gold = _gold(p, tr)
        if gold < RECALL_GOLD:
            continue
        ts = spans.get(int(tr), int(tr))
        delay = tr - ts
        v = advantage(p, ts)
        obj = in_play(p, ts)
        at_once = sorted({c["champion"] for c in _recalls(p) if c["team"] == p.team and c["champion"] != p.champion and not c["cancelled"]
                           and ts - SYNC <= c["time"] <= ts + SYNC + LATE_RECALL})
        taken = p.earns(ts, tr) or [c for c in _mine(p) if ts <= c["time"] <= tr and c.get("side") != _side(p) and c["camp"] in (*C.CAMPS, "Blue", "Red")]
        if delay > LATE_RECALL and not taken:  # if in that time they got kills, objectives or invasions, they didn't lose it
            what = p.activity(ts, tr)
            doing = C._list([f"{C._duration(s)} {where}" for where, s in what[:2]])
            cleared_ones = [f"{c['camp']} {C._clock(c['time'])}" for c in _mine(p) if ts <= c["time"] <= tr and c.get("side") == _side(p)]
            text = (f"At {C._clock(ts)} you had {_gold(p, ts):,.0f} g, enough for a full item, and you kept going for {C._duration(delay)} "
                     f"({doing}{'; cleared ' + C._list(cleared_ones) if cleared_ones else ''}) before recalling at {C._clock(tr)}. The window to recall is "
                     "set by the gold, your teammates' tempo (you want to open the map all together) and the objective timers. ")
            text += (f"{C._list(at_once)} recalled around then. " if at_once else "Nobody on your team was recalling around then. ")
            text += (f"{obj['text'][0].upper() + obj['text'][1:]} {'had been up since ' + C._clock(obj['leaves']) if obj['missing'] <= 0 else 'spawned in ' + C._duration(obj['missing'])}. "
                      if obj else "No objective was close. ")
            text += f"And {_advantage_txt(v)}."
            severity = (IMPORTANCE["HIGH"] if len(at_once) >= 2 and obj and v["ahead"] else
                        IMPORTANCE["MEDIA"] if obj or len(at_once) >= 2 else IMPORTANCE["LOW"])
            when = min((c["time"] for c in _recalls(p) if c["team"] == p.team and c["champion"] in at_once and ts - SYNC <= c["time"]), default=ts)
            missed_window = max(float(ts), when)
            out.append(C._moment(p, missed_window, p.where(p.champion, missed_window), "back", "bad", severity, "Missed the recall window", text,
                                    end=float(tr)))
            worst = severity
        late = delay > LATE_RECALL and not taken
        out.append(C._moment(p, tr, p.where(p.champion, tr), "back", "good", IMPORTANCE["HIGH"] if late and worst == IMPORTANCE["HIGH"] else IMPORTANCE["MEDIA"],
                                "Recalled with gold to spend" if not late else "Recalled, late but right",
                                f"You recalled at {C._clock(tr)} with {gold:,.0f} g to spend. "
                                + ("It is not the first window you had" + f" (that was at {C._clock(ts)})" + ", but it is better than staying on the map with all that gold."
                                   if late else "Back with the gold, the shop and your team's tempo: you can open the map ready."),
                                end=float(tr)))
    # the cancelled recalls that end in a completed one
    cancelled_ones = [r for r in _recalls(p) if r["champion"] == p.champion and r["cancelled"] and r["time"] > 120]
    for group in C._streaks([{"t": r["time"], "r": r} for r in cancelled_ones], gap=40.0):
        a, b = group[0]["t"], group[-1]["t"]
        then = next((r for r in mine_list if not r["cancelled"] and b < r["time"] <= b + 90), None)
        if not then:
            continue
        obj, v = in_play(p, a, before=60.0), advantage(p, a)
        near = min((r["r"]["rival_near"] for r in group if r["r"]["rival_near"] != ""), default=None)
        bad_ = bool(obj and v["ahead"])
        text = (f"You started a recall at {C._clock(a)}"
                 + (f" and again at {C._list([C._clock(g['t']) for g in group[1:]])}" if len(group) > 1 else "")
                 + f" and cancelled {'them' if len(group) > 1 else 'it'}; you finally recalled at {C._clock(then['time'])}, {C._duration(then['time'] - a)} later."
                 + (f" An enemy was {near:,} units away." if near not in (None, "") else ""))
        if obj:
            text += f" {obj['text'][0].upper() + obj['text'][1:]} {'spawned' if obj['missing'] <= 0 else 'spawns'} at {C._clock(obj['leaves'])}."
        text += f" And {_advantage_txt(v)}."
        if bad_:
            text += (" Cancelling a recall for a stimulus that is there now, without counting that the play that gives you the most win "
                      "probability is to go back and be at the objective, is what delays the snowball. Keep casting the recall, or cast it where nobody "
                      "will cancel it.")
        out.append(C._moment(p, a, p.where(p.champion, a), "back", "bad" if bad_ else "neutral",
                                IMPORTANCE["MEDIA"] if bad_ else IMPORTANCE["LOW"], "Cancelled the recall", text, end=float(then["time"])))
    return out


# ── With an advantage: opening and the numerical advantage ────────────────────────────────────────────────

def adjust_openings(p: C.Game, moment_list: list[dict]) -> None:
    """With an advantage and an objective in play (or about to spawn), opening the map to camps instead of to the fight or the objective is the usual opening
    with the priority changed: it stays as the moment, with its text, and the tone drops one step."""
    if p.position != "JUNGLE":
        return
    for m in moment_list:
        if m["kind"] != "opening" or m.get("first") not in ("camp", "invasion"):
            continue
        v = advantage(p, m["t"])
        obj = in_play(p, m["t"], before=30.0)
        if not (v["ahead"] and obj):
            continue
        already = obj["missing"] <= 0
        m["text"] += (f" But {_advantage_txt(v)}, and {obj['text']} {('were' if obj['name'] == 'Voidgrub' else 'was') + ' already up' if already else 'spawned ' + C._duration(obj['missing']) + ' later'}: "
                      "with the lead the priority is no longer your camps but the objective and the fights you can win, connecting with your lanes "
                      "and going together. Opening straight to the objective is what snowballs the lead.")
        m["tone"] = "bad" if already else "neutral"
        m["severity"] = IMPORTANCE["LOW"]


def numerical_advantage(p: C.Game) -> list[dict]:
    """While the enemy jungler is dead and you are ahead, what is called for is invading, taking their camps or pressuring a lane: farming your own is
    delaying the snowball."""
    if p.position != "JUNGLE" or not p.rival:
        return []
    rival_net = next(j["net_id"] for j in p.events["players"] if j["champion"] == p.rival)
    side, other = _side(p), "red" if _side(p) == "blue" else "blue"
    out = []
    for e in p.events["events"]:
        if e["type"] != "Death" or e["net_id"] != rival_net or not 360 <= e["time"] <= 1200 or e.get("respawn_time", 0) < 15:
            continue
        t0, t1 = e["time"], e["time"] + e["respawn_time"]
        v = advantage(p, t0)
        if not v["ahead"] or not p.is_alive(p.champion, t0):
            continue
        mine_total = [(c["time"], c["camp"], c.get("side")) for c in _mine(p) if t0 <= c["time"] <= t1 + 5]
        own_ones = [(t, c) for t, c, side_ in mine_total if side_ == side and c in (*C.CAMPS, "Blue", "Red")]
        does_something = [x for x in mine_total if x[2] == other or x[1] in ("Voidgrub", "Herald", "Baron") or x[1].startswith("Dragon")]
        team_objective = [o for o in p.objectives if t0 <= o["t"] <= t1 + 10 and o["team"] == p.team]
        kills = [k for k in p.kills if t0 <= k["t"] <= t1 and p.champion in (k["killer"], *k["assists"])]
        goes_back = any(r["champion"] == p.champion and t0 <= r["time"] <= t1 for r in _recalls(p))
        if not own_ones or does_something or team_objective or kills or goes_back:
            continue
        text = (f"{p.rival} died at {C._clock(t0)} and couldn't act until {C._clock(t1)}. {_advantage_txt(v)[0].upper() + _advantage_txt(v)[1:]}. "
                 f"In that window you cleared your own {C._list([f'{c} {C._clock(t)}' for t, c in own_ones])} instead of using the empty map: with the "
                 "lead and their jungler dead you can invade and take their camps, get vision around a lane and look for a catch, and every second "
                 "you spend on your own camps is a second the snowball is delayed.")
        out.append(C._moment(p, t0, p.where(p.champion, t0), "play", "bad", IMPORTANCE["MEDIA"], "Used their jungler's death to farm your own camps",
                                text, end=float(t1)))
    return out


# ── The upgraded smite ────────────────────────────────────────────────────────────────────────────────────

def upgraded_smite(p: C.Game) -> list[dict]:
    """The jungle item's pet: a charge per large monster killed, plus an extra one for each stored charge (one arrives every 60 s);
    at 15 it evolves and the Smite becomes the upgraded one. If what completes it is killed by spending the Smite right before, the upgraded one is born with the spell
    on cooldown when the crab and the dragon spawn."""
    if p.position != "JUNGLE":
        return []
    smites = sorted(e["time"] for e in p.events["events"] if e["type"] == "CastSpell" and e["net_id"] == p.me["net_id"] and e["spell"] == "SummonerSmite")
    purchase = next((e["time"] for e in p.events["events"] if e["type"] == "BuyItem" and e["net_id"] == p.me["net_id"] and e["item_id"] in (1101, 1102, 1103)), 10.0)
    treats, used_ones = 0, 0
    for c in sorted((c for c in _mine(p) if c["camp"] in BIG and c.get("side") == _side(p)), key=lambda c: c["time"]):
        stored = int((c["time"] - purchase) // 60) - used_ones
        extra = 1 if stored > 0 else 0
        used_ones += extra
        treats += 1 + extra
        if treats < EVOLUTION:
            continue
        spending = next((s for s in smites if c["time"] - 20 <= s <= c["time"]), None)
        if spending is None:
            return []
        goes_back = next((s for s in smites if s > c["time"]), None)
        soon = [o for o in (*objectives(p),) if o["name"] == "Dragon" and o["leaves"] <= c["time"] + 90 and o["falls"] > c["time"]]
        crabs = [e["time"] for e in p.events["events"] if e["type"] == "SpawnNeutral" and (e.get("character") or "").lower() == "sru_crab"
                     and c["time"] < e["time"] <= c["time"] + 60]
        if not soon and not crabs:
            return []
        text = (f"The {c['camp']} you killed at {C._clock(c['time'])} was your {treats}th treat (one per large monster, plus one for each stored bonus treat): "
                 f"the pet evolves at {EVOLUTION} and your Smite becomes the Unleashed Smite. But you spent your Smite on it at {C._clock(spending)}, so you "
                 f"reached the evolution with the spell on cooldown just when {C._list(([f'the Scuttle spawned at {C._clock(crabs[0])}'] if crabs else []) + ([f'the Dragon was up since {C._clock(soon[0]['leaves'])}'] if soon else []))}. "
                 "Killing it a few seconds later without Smite, you get the upgraded Smite ready for the Scuttle, the level 6 a contested Scuttle gives "
                 "and a lead over their jungler that lasts until his first camp respawns: a free Dragon. It also applies to the Krugs, the last camp "
                 "of the clear before the second Scuttle.")
        return [C._moment(p, c["time"], p.where(p.champion, c["time"]), "camps", "bad", IMPORTANCE["MEDIA"], "Smite spent on the camp that evolved the pet", text,
                           treats=treats)]
    return []


# ── The net result of a play ──────────────────────────────────────────────────────────────────────────────

def _net_by_position(p: C.Game, a: float, b: float) -> list[tuple[str, float, float]]:
    """Per position, how much their team's gold and XP rise over the window against the opponent of the same position: the difference of differences,
    which leaves out the advantage that was there before."""
    out = []
    for position in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
        mine, opp = C._of(p, p.team, position), C._of(p, p.rival_team, position)
        a1, a2, b1, b2 = _row(p, mine, a), _row(p, opp, a), _row(p, mine, b), _row(p, opp, b)
        if not (a1 and a2 and b1 and b2):
            continue
        gold = (C._num(b1, "total_gold") - C._num(a1, "total_gold")) - (C._num(b2, "total_gold") - C._num(a2, "total_gold"))
        xp = (C._num(b1, "xp") - C._num(a1, "xp")) - (C._num(b2, "xp") - C._num(a2, "xp"))
        out.append((position, gold, xp))
    return out


POSITION_NAME = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "mid", "BOTTOM": "ADC", "UTILITY": "support"}


def net_of_plays(p: C.Game, moment_list: list[dict]) -> None:
    """A death, a camp left half done or a camp stolen INSIDE a play or a fight that paid off isn't a separate mistake: the play's result
    already includes them. The window is isolated (what each position rises against their opponent, without the earlier advantage) and the tone is lowered."""
    if p.position != "JUNGLE":
        return
    good_ones = [m for m in moment_list if m["kind"] in ("play", "fight") and m["tone"] == "good" and m.get("end") is not None]
    for m in moment_list:
        stolen_ = m["kind"] == "camps" and "stolen" in m["title"]
        if m["tone"] != "bad" or not (m["kind"] in ("death", "pair") or stolen_):
            continue
        inside = next((g for g in good_ones if g["t"] - 5 <= m["t"] <= g["end"] + (25 if g["kind"] == "play" else 5)), None)
        if inside is None:
            continue
        net = _net_by_position(p, inside["t"] - 5, inside["end"] + 10)
        gold, xp = sum(o for _p, o, _x in net), sum(x for _p, _o, x in net)
        paid_ = (play_ := inside.get("play")) and play_["objectives"] and play_["value"] > 0
        if gold <= 0 and xp <= 0 and not paid_:
            continue
        by_position = C._list([f"{POSITION_NAME[pu]} {o:+,.0f} g / {x:+,.0f} XP" for pu, o, x in net])
        with_objective = ""
        if (play := inside.get("play")) and play["objectives"]:
            with_objective = f" With the objective it is worth {play['value']:+,d} g for your side."
        m["text"] += (f" It happened inside {inside['title'].lower()} at {inside['clock']}, and the net result of that window for your side against theirs, "
                      f"position against position, is {gold:+,.0f} g and {xp:+,.0f} XP ({by_position}).{with_objective} The cost belongs to that play, which "
                      "paid, so it is not counted on its own.")
        m["tone"], m["severity"] = "neutral", 1
        m["inside"] = {"clock": inside["clock"], "title": inside["title"], "net_gold": round(gold), "net_xp": round(xp)}


def far_from_herald(p: C.Game, moment_list: list[dict]) -> None:
    """Being far from an objective «for a reason» becomes bad when in that time there was a cancelled recall with an advantage."""
    cancelled_ones = [m for m in moment_list if m["kind"] == "back" and m["title"] == "Cancelled the recall" and m["tone"] == "bad"]
    for m in moment_list:
        if m["kind"] == "setup" and m["tone"] == "neutral" and "being away had a reason" in m["text"]:
            c = next((c for c in cancelled_ones if m["t"] <= c["t"] <= (m.get("end") or m["t"])), None)
            if c:
                m["text"] += (f" Part of that time is the recall you cancelled at {c['clock']}: with the lead, the objective is the priority, and a "
                              "kill-less chase isn't worth missing it.")
                m["tone"], m["severity"] = "bad", IMPORTANCE["MEDIA"]


def everything(p: C.Game) -> list[dict]:
    """The new jungle moments (not scored until they are calibrated with more reviews)."""
    if p.position != "JUNGLE":
        return []
    return (first_clear(p) + crab(p) + info_you_give(p) + recall_windows(p) + numerical_advantage(p) + upgraded_smite(p))
