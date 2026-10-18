"""The minimal check of fights and health lost (moments.py), with an invented match.

    python research/replays/test_fights.py
"""
import moments as M

players = [{"net_id": f"n{i}", "champion": f"c{i}", "team": "100" if i < 5 else "200", "position": "BOTTOM"}
             for i in range(10)]
# every second, all together in the same place and with health dropping 10 per second
rows = {p["champion"]: [{"time": str(s), "x": "1000", "z": "1000", "alive": "True", "health": str(500 - 10 * s),
                          "total_gold": "3000" if p["team"] == "100" else "1000", "gold": "0"} for s in range(30)]
         for p in players}
def hit(t, source, a):
    return {"type": "Damage", "time": t, "net_id": f"n{a}", "source": f"n{source}", "amount": 100.0}


events = {"players": players, "camps": [], "events": [
    *[hit(1.0 + i, i, 9 - i) for i in range(5)],  # 1-5 s: all ten fight → teamfight
    hit(20.0, 0, 5), hit(21.0, 5, 0),  # 20 s, past the gap: a 1v1 → skirmish
]}

p = M.fights(events, rows)
assert [x["take_part"] for x in p] == [10, 2], p
assert [x["teamfight"] for x in p] == [1, 0]
assert p[0]["lower"] == "200"  # 5 x 1000 against 5 x 3000 gold in items
assert M._loss(M._table(events, rows)["c0"], range(1, 11)) == 100.0
print("ok")

# timers: dragon at 5:00; falls at 6:00 → the next at 11:00.
timers = M._timers({"camps": [{"camp": "Dragon (fire)", "time": 360.0}]})
assert timers == [(300.0, 360.0, "Dragon"), (660.0, float("inf"), "Dragon")], timers
print("timers ok")

# a Gromp with no place (the decoder leaves it at (0, 0) and counts it as blue): it comes out where its monster was born, on the red side
events = {"camps": [{"camp": "Gromp", "side": "blue", "time": 186.56, "killer": "k", "position": [0, 0]}], "events": [
    {"type": "SpawnNeutral", "time": 90.0, "net_id": "g", "character": "SRU_Gromp", "position": [12626, 6434]},
    {"type": "UnitDeath", "time": 186.56, "net_id": "g", "killer": "k", "position": [0, 0]}]}
gromp, = M.drop_revived(events)["camps"]
assert gromp["position"] == [12626, 6434] and gromp["side"] == "red", gromp
print("camps ok")

# a theft and an invasion: the blue Gromp that the red jungler clears is a theft for blue (and not a stalled
# camp), and the red Raptors that blue clears, an invasion of theirs
players = [{"net_id": "a", "champion": "Blue", "team": "100", "position": "JUNGLE"},
             {"net_id": "r", "champion": "Red", "team": "200", "position": "JUNGLE"}]
fields = [{"camp": "Gromp", "side": "blue", "time": 100.0, "killer": "a", "position": [2100, 8400]},
          {"camp": "Gromp", "side": "blue", "time": 240.0, "killer": "r", "position": [2100, 8400]},
          {"camp": "Raptors", "side": "red", "time": 300.0, "killer": "a", "position": [7800, 9800]}]
idle = M.idle_jungle({"players": players, "camps": fields, "events": [], "game_length": 400.0}, {},
                         period=135.0, until=400.0)
assert (idle["Blue"]["stolen"], idle["Blue"]["invade"]) == (1, 1), idle["Blue"]
assert idle["Blue"]["thefts"][0]["who"] == "Red" and idle["Red"]["stolen"] == 1  # the red Raptors
assert idle["Blue"]["lost_and_stolen"] == idle["Blue"]["clears_lost"] + 1
print("thefts ok")

# pairs: the Raptors without the Krugs in 45 s break the pair; the Wolves with the Gromp 20 s later, don't
spawned_at = [{"type": "SpawnNeutral", "time": 90.0, "net_id": n, "character": c, "position": p}
        for n, c, p in (("k", "SRU_Krug", [8400, 2700]), ("z", "SRU_Razorbeak", [7000, 5400]),
                        ("w", "SRU_Murkwolf", [3800, 6500]), ("g", "SRU_Gromp", [2100, 8400]))]
fields = [{"camp": "Raptors", "side": "blue", "time": 120.0, "killer": "a", "position": [7000, 5400]},
          {"camp": "Wolves", "side": "blue", "time": 140.0, "killer": "a", "position": [3800, 6500]},
          {"camp": "Gromp", "side": "blue", "time": 160.0, "killer": "a", "position": [2100, 8400]},
          {"camp": "Krugs", "side": "blue", "time": 220.0, "killer": "a", "position": [8400, 2700]}]
pairs = M.camp_pairs({"players": players, "camps": fields, "events": spawned_at, "game_length": 400.0}, {})["Blue"]
assert (pairs["clears"], pairs["paired"], pairs["broken"]) == (4, 2, 1), pairs  # the Krugs, already unpaired
assert pairs["detail"] == [{"t": 120.0, "camp": "Raptors", "duo": "Krugs", "did": "other camp",
                             "wait": 100.0}], pairs["detail"]
print("pairs ok")

# the pressure reaches up to PRESSURE: the enemy mid who goes back to base with the jungler in view at 2000 counts; the top who
# goes back to base with the jungler at 6000, doesn't
def row(s, x, z, seen="True"):
    return {"time": str(s), "x": str(x), "z": str(z), "alive": "True", "seen": seen}


table = {"Blue": {s: row(s, 6000, 6000) for s in range(100, 121)},
         "Mid": {s: row(s, 7400, 7400) for s in range(100, 121)},
         "Top": {s: row(s, 2000, 12000) for s in range(100, 121)}}
state = {"corridors": {(int(x // M.CELL), int(z // M.CELL)): {c} for x, z, c in ((7400, 7400, "mid"), (2000, 12000, "top"))},
          "axis": {"mid": {"blue": 3000.0, "red": 26000.0}, "top": {"blue": 3000.0, "red": 26000.0}}}
rivals = [{"champion": "Mid", "team": "200", "position": "MIDDLE"}, {"champion": "Top", "team": "200", "position": "TOP"}]
go_back = {"Mid": [112.0], "Top": [112.0]}
assert M._pressured(table, state, "Blue", rivals, go_back, 105, 115, 8.0) == [("Mid", "mid", "goes back to base")]
assert not M._pressured({**table, "Blue": {s: row(s, 6000, 6000, "False") for s in range(100, 121)}}, state, "Blue",
                          rivals, go_back, 105, 115, 8.0)  # if they aren't seen, it pressures nobody
assert M._gets_burned("SummonerFlash") and not M._gets_burned("SummonerSmite") and not M._gets_burned("S5_SummonerSmitePlayerGanker")
print("pressure ok")

# the support item: 3 charges on transforming, spent on placing wards and only returning at the shop
support_ = [{"net_id": "s", "champion": "Sup", "team": "100", "position": "UTILITY"}]
rows_s = {"Sup": [{"time": str(s), "x": "400" if s < 5 or 60 <= s < 70 else "9000", "z": "400" if s < 5 or 60 <= s < 70 else "2000",
                    "alive": "True", "team": "100"} for s in range(0, 100)],
           "Other": [{"time": str(s), "x": "14300", "z": "14400", "alive": "True", "team": "200"} for s in range(0, 100)]}
events_s = {"players": support_, "game_length": 99.0, "events": [
    {"type": "BuyItem", "time": 10.0, "net_id": "s", "item_id": 3866},
    *[{"type": "CastSpell", "time": t, "net_id": "s", "spell": "ItemGhostWard"} for t in (20.0, 25.0, 30.0, 80.0)]]}
own, = M.support_item(events_s, rows_s)
# empty from 30 to 59 (goes back to the shop at 60, with the three spent) and with two charges at the end
assert (own["wards"], own["empty"], own["trips"], own["charges_wasted"]) == (4, 30, 1, 0), own
assert own["spans_empty"] == [[30, 59]] and own["returns"] == [[60, 0]], own
print("support item ok")
