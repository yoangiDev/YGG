# The jungler's routes: what it does after each camp and what it is worth — all games

**5,264 games** decoded (the 16.18 and 16.19 ladder, from Gold to Challenger, and the users' uploads) and **256,092
decisions**: which camp each jungler starts with and what it does after each camp it kills until 14:00. 5,143 games have the
per-second WP (`wp_per_second.npz`) to measure what each route is worth. It comes from `routes.py` and `routes_model.py` (usage in
their docstrings); the complete tables stay in `research/ladder/data/routes2/analyse.md`. **It is not integrated into the app.**

The idea: not to pronounce which play is the right one, but to see **in each game state which routes junglers choose and what
each one yields**, without hand-written rules.

**Second version.** Three changes over the first:

1. **Three horizons**: what happens at 90 s, 3 min and 5 min. The first only looked at 90 s.
2. **The counter-gank** as a route, and where the enemy jungler is at each decision.
3. **Each route is compared with the others in the same state** (the same moment and the same health and unspent gold). The first
   version compared them with the moment's average, and that mixed going back to base with being at low health (below, in
   Method).

---

## The essentials

1. **What the good players choose in each state is learned well.** The Master-and-above policy gets the most likely route right
   62.7% of the time, against 52.1% for sticking with the most frequent one at each moment, validated by game (log-loss 1.161
   against 1.562; now with the counter-gank, there are more routes to choose among).
2. **At 5 minutes, some routes are worth more than they seemed at 90 s**:
   - **Invading**: after the 2nd camp, +1.9 WP points at 90 s, **+2.7 at 5 min**. From the 7th camp on, −0.2 at 90 s (can't be
     told apart from zero) but **+1.0 at 5 min** and +119 gold against the enemy jungler. At 90 s you saw what going costs; at 5
     min, what was taken from the enemy.
   - **The scuttle crab** (from the 7th on): +0.3 at 90 s, **+1.2 at 5 min**.
   - **Ganking bot with the enemy ahead** (from the 3rd to the 6th camp), against continuing to clear: +0.9 at 90 s, **+2.3 at 5
     min**. **With prio, the same gank costs −2.5 at 5 min.** And ganking mid with prio, −4.6.
3. **Going back to base: what costs isn't the horizon, it is going back without gold.** From the 7th camp on, going back costs about
   0.4 points against continuing to clear at 90 s, at 3 min and at 5 min: it isn't recovered. But almost all of it comes from going
   back **with half health or more and under 800 gold**: −1.8 at 90 s and −2.0 at 5 min. **With 1,300 gold or more, or with under
   half health, going back can't be told apart from continuing to clear.** The first version said going back came out expensive
   because at 90 s you can't see what is bought; with 5 minutes in view, that was only partly true.
4. **The counter-gank pays off, but with risk.** When the enemy jungler goes to gank a lane, going to that lane against continuing to
   clear is worth **+1.0 in bot** (at 90 s and at 5 min) and **+0.7 in mid** (at 90 s), in exchange for 14-16% more risk of dying.
   Against invading the other side of the jungle it wins at 90 s, but at 5 min they tie, and the invasion leaves more gold. Against
   going back to base, from +1.2 to +2.1. It is only done 5 to 8% of the time (the same in Master+), and only in one of five of
   those decisions did their team see it beforehand.
5. **What can't be done yet: the value of each route state by state.** With 5,000 games, no model predicts a route's value according
   to the state better than that route's average. **Looking further doesn't help**: at 5 min there is more signal, but also more
   noise. The risk of dying according to the state is learned in the frequent routes.

---

## Method

### The decision and the route

- **Decision 0**: when the camps spawn (0:55 in 16.19 and 16.20). The route is the first camp it kills.
- **Decision k**: each camp it kills (its own, the enemy's, the crab or an epic; consecutive grubs count once), until 14:00. The
  route is **the first thing it does in the next 75 s**:

| route | what marks it |
|---|---|
| camp | kills another camp of its own (in the first two decisions, with its name) |
| invade | kills an enemy camp |
| crab / objective | kills the crab / an epic |
| gank top, mid or bot | hits an enemy while in that lane's corridor, or spends 4 s in a row in it with an enemy of that lane within 1,500 |
| **counter-gank top, mid or bot** | the same gank, when the enemy jungler was already in that lane (within 3,000 of where it arrives) in the previous 20 s |
| fight | hits an enemy in the jungle or the river |
| base | starts a recall that ends in the base |

Of the 29,330 ganks, 6,019 are counter-ganks (3,042 in mid, 1,964 in bot and 1,013 in top). In 72% of them the enemy jungler shows up
next to one of its own in that lane within 30 s after the decision; the rest is the enemy jungler in the lane without reaching to
gank (pushing with its laner, for example).

### The state

What the jungler knew at that second, that of `openings.state`: the camps of each half (alive and those that spawn in 30 s), the
crab, the upcoming objective, each lane (the enemies' health and flash, the allies' health and ultimates, where the wave is, gold)
and where and how long ago the enemy jungler was seen. **New**: in which lane their team saw it in the last 10 s. Plus their own:
level, health, mana, unspent gold, smite, the camp it just killed, how long it has been away from base, its champion and the enemy's,
and the league.

What the player didn't know enters no model: where the enemy jungler really was and, **new**, in which lane it is going to gank in the
next 30 s (`rival_ganks`). The latter only serves to split the tables: comparing, among the decisions in which the enemy was going to
gank bot, whoever went to bot with whoever kept clearing.

### The route's value, in the same state

For each outcome (its team's WP, whether it dies and the gold against the enemy jungler, at each horizon) a model learns **without
the route** what usually happens after a state like that, out of fold by game. The residual is what came out minus that.

**New.** That model isn't calibrated in all states. With under half health, what comes out exceeds the expected by almost a WP point,
whatever is done. A less regularised model doesn't fix it: it predicts worse out of fold and the bias stays. Since going back to base
is mostly chosen at low health, comparing it with the moment's average mixed it with that bias. So each residual is centred on its
**cell**: the moment (each of the first six camps, or the 7th on) and the health and gold state:

- under half health;
- half health or more, and under 800 unspent gold;
- half health or more, and 800 to 1,299;
- half health or more, and 1,300 or more.

The tables compare each route with the other decisions in its cell, with 90% intervals resampling whole games. The averages by moment
barely change from the first version (going back to base, from the 7th on, goes from −0.69 to −0.61). What changes is a game's tree
(below).

**The horizons.** 90 s is the immediate: the gank, the fight, the time lost on going back. At 3 and 5 min you also see what going back
buys or what the invaded enemy stops doing. But at 5 min what it did afterwards also counts, so it is "what happens after choosing
that route", not just the route. At the first camp, the 90 s one reaches 3:45 (the end of the first clear).

What is expected is poorly predicted: out-of-fold R² of 0.032, 0.040 and 0.044 for the WP at 90 s, 3 and 5 min. A few minutes of game
are mostly noise, and that is why thousands of cases are needed to see a route's average.

---

## What they choose and what it yields

Neutral WP points of its team against the decisions in its same cell (a kill is worth about 4.7). In bold, what doesn't cross zero.

### The first camp

| route | choose it | Gold-Plat. | Master+ | WP at 90 s | WP at 3 min | WP at 5 min | it dies |
|---|---|---|---|---|---|---|---|
| Blue | 38% | 45% | 31% | 0.00 | −0.03 | −0.16 | −0.1% |
| Red | 27% | 25% | 29% | −0.16 | −0.14 | −0.11 | −2.0% |
| Raptors | 26% | 22% | 31% | +0.03 | −0.04 | 0.00 | 0.0% |
| Wolves | 3% | 2% | 4% | −0.75 | **−0.90** | −1.26 | +4.5% |
| invade Raptors | 2% | 2% | 2% | **+1.76** | **+2.04** | **+2.00** | +5.7% |

None of the three usual ones can be told apart from the others at any horizon. What changes is the league: Master and above start more
with Raptors (31% against 22%) and less with Blue (31% against 45%).

### After the 2nd camp

| route | choose it | WP at 90 s | WP at 3 min | WP at 5 min | it dies | gold against the enemy jungler (5 min) |
|---|---|---|---|---|---|---|
| camp | 92% | **−0.10** | **−0.13** | **−0.14** | −1.2% | −7 |
| invade | 4% | **+1.89** [+1.31, +2.47] | **+2.64** | **+2.71** [+1.53, +3.94] | +6.7% | **+126** |
| fight | 2% | +0.03 | −0.70 | **−1.98** | **+27.2%** | −19 |

### After the 3rd camp

| route | choose it | Gold-Plat. | Master+ | WP at 90 s | WP at 3 min | WP at 5 min | it dies |
|---|---|---|---|---|---|---|---|
| camp | 74% | 75% | 72% | −0.10 | **−0.17** | −0.14 | −2.7% |
| base | 7% | 4% | **11%** | −0.13 | −0.34 | −0.56 | −4.8% |
| fight | 5% | 5% | 6% | **+0.68** | **+1.24** | **+2.37** | **+20.1%** |
| gank bot | 3% | 3% | 3% | **+1.84** | **+2.75** | +1.87 | +12.4% |
| gank top | 3% | 3% | 3% | +0.31 | +0.90 | −0.09 | +7.3% |
| invade | 3% | 3% | 2% | +0.49 | **+1.63** | +1.65 | +9.1% |
| gank mid | 2% | 3% | 1% | −0.93 | **−1.52** | **−2.11** | +11.1% |

After the third camp the high leagues go back to base almost three times as much as Gold and Platinum (11% against 4%), and that can't
be told apart from continuing to clear. They gank mid much less (1% against 3%): ganking mid there costs 2 points at 5 min.

### From the 7th camp to 14:00 (182,406 decisions)

| route | choose it | WP at 90 s | WP at 3 min | WP at 5 min | it dies | gold against the enemy jungler (5 min) |
|---|---|---|---|---|---|---|
| camp | 48% | **−0.17** | **−0.28** | **−0.32** | −4.7% | −2 |
| fight | 18% | **+0.11** | +0.10 | +0.14 | **+15.0%** | −9 |
| base | 9% | **−0.61** | **−0.69** | **−0.77** | −7.6% | **−40** |
| crab | 4% | **+0.27** | **+0.75** | **+1.16** [+0.70, +1.59] | −4.0% | **+42** |
| gank mid / bot / top | 4 / 4 / 3% | +0.13 / +0.07 / −0.02 | +0.12 / **+0.41** / +0.17 | +0.10 / −0.09 / −0.14 | +3.4 / +4.7 / +1.4% | −5 / +26 / +20 |
| invade | 4% | −0.24 | **+0.39** | **+0.98** [+0.48, +1.50] | −2.5% | **+119** |
| objective | 3% | **+2.86** | **+2.79** | **+2.99** | −4.0% | −41 |
| counter-gank mid | 1% | +0.27 | +0.35 | +0.37 | +6.0% | +12 |

**The objective comes out very positive** because the route and the outcome are the same thing: taking a dragon raises the WP. It
serves to see that it was chosen, not to compare it with the others.

---

## Going back to base

Going back minus continuing to clear, in the same state:

| when | state | go back | WP at 90 s | WP at 3 min | WP at 5 min | it dies | gold against the enemy jungler (90 s / 5 min) |
|---|---|---|---|---|---|---|---|
| after the 3rd | all | 7% | −0.03 | −0.17 | −0.42 | −2.1% | 0 / +21 |
| after the 6th | all | 6% | −0.61 | −0.79 | −0.23 | −5.7% | **−38** / −24 |
| from the 7th to 14:00 | all | 9% | **−0.43** | **−0.41** | **−0.45** | −2.9% | **−33 / −38** |
| from the 7th | **half health or more, under 800 gold** | 3% | **−1.79** [−2.14, −1.44] | **−1.70** | **−1.97** [−2.61, −1.38] | −5.1% | **−80 / −102** |
| from the 7th | 800 to 1,299 gold | 15% | −0.18 | −0.28 | −0.39 | −3.2% | **−34 / −46** |
| from the 7th | 1,300 to 1,999 gold | 22% | +0.09 | +0.11 | +0.42 | −0.7% | −10 / 0 |
| from the 7th | 2,000 gold or more | 28% | +0.49 | +0.73 | +0.33 | +2.3% | +25 / +41 |
| from the 7th | under half health | 19% | −0.44 | −0.15 | +0.20 | −0.6% | **−24** / +15 |

("Go back" is the share of that state's decisions that go back; the gold states count any health.)

What comes out is what coaches teach, and nobody told the model:

- **Going back with little gold and good health is throwing time away.** It costs almost 2 points and 100 gold against the enemy
  jungler at 5 min, and isn't recovered.
- **With something to buy (1,300 or more), or at low health**, going back can't be told apart from continuing to clear, with some
  advantage at 5 min that doesn't become clear.
- **The back after the third camp** (11% of the high league) costs nothing.

---

## The state changes the route's value

### Ganking or continuing to clear, according to the wave (from the 3rd to the 6th camp)

Gank minus continuing to clear, in the same state of that lane:

| lane | state | gank | WP at 90 s | WP at 5 min | it dies | gold against the enemy jungler (5 min) |
|---|---|---|---|---|---|---|
| bot | enemy ahead | 4.0% | **+0.94** [+0.19, +1.64] | **+2.26** [+0.79, +3.86] | +7.9% | **+121** |
| bot | enemy ahead and without flash | 3.9% | +1.06 | **+2.93** | +11.7% | **+113** |
| bot | with prio | 1.5% | −0.15 | **−2.48** [−4.56, −0.18] | **+11.3%** | +31 |
| top | enemy ahead | 3.1% | 0.00 | +0.51 | +4.8% | **+83** |
| top | with prio | 1.0% | +1.11 | +0.92 | **+13.5%** | +57 |
| mid | enemy ahead | 3.3% | −0.41 | −1.60 | +7.6% | +7 |
| mid | with prio | 0.9% | **−1.44** | **−4.56** [−7.83, −1.81] | +7.7% | −86 |

**Enemy ahead**: the wave in its team's half (≤ 0.45), so that the enemies of that lane play far from their tower. **With prio**: the
wave in the enemy half (≥ 0.55). At 5 min the difference widens: the bot gank with the enemy pushed past is worth double that at 90 s,
and the same gank with prio goes from being indistinguishable to costing 2.5.

### Counter-ganking or carrying on with its own (from the 2nd camp)

Decisions in which the enemy jungler shows up in that lane, next to one of its own, in the next 30 s. Counter-gank minus the other
route, in the same state:

| lane | decisions | they saw it | counter-gank (Master+) | against | WP at 90 s | WP at 5 min | it dies | gold (5 min) |
|---|---|---|---|---|---|---|---|---|
| bot | 21,955 | 19% | 7.7% (7.4%) | continuing to clear | **+1.05** [+0.45, +1.63] | **+1.03** [+0.06, +1.96] | **+15.6%** | **+47** |
| | | | | invade | **+1.70** | −0.09 | +15.9% | **−57** |
| | | | | go back to base | **+2.11** | **+1.76** | +19.9% | **+90** |
| | | | | gank another lane | **+0.75** | +0.90 | +15.8% | **+51** |
| mid | 21,637 | 16% | 8.4% (8.7%) | continuing to clear | **+0.72** [+0.26, +1.16] | +0.56 | **+13.6%** | +32 |
| | | | | invade | **+0.89** | −0.85 | +9.5% | **−99** |
| | | | | go back to base | **+1.60** | **+2.18** | +17.1% | **+149** |
| | | | | gank another lane | +0.54 | +0.12 | +7.7% | +15 |
| top | 15,713 | 18% | 5.1% (5.3%) | continuing to clear | +0.58 | +1.10 | **+15.5%** | +32 |
| | | | | invade | +0.75 | +0.20 | +13.6% | −44 |
| | | | | go back to base | **+1.16** | **+1.97** | +19.3% | +54 |

**They saw it**: their team saw it in that lane in the previous 10 s. The two textbook answers to the enemy's gank come out equal at 5
min: **going to the lane** (wins at 90 s, with much more risk of dying) or **invading the other side** (more gold, less risk). What
comes out expensive is going back to base while the enemy ganks.

---

## What can't be done yet: the value state by state

A model of each route's value according to the state (one per route, over what is left after the expected), validated by game, against
the route's average. An R² below zero is predicting worse than the average:

| route | decisions | R² at 90 s | R² at 3 min | R² at 5 min | risk of dying according to the state: log-loss average → model |
|---|---|---|---|---|---|
| camp | 123,186 | −0.004 | −0.009 | −0.015 | 0.457 → **0.439** |
| fight | 38,021 | −0.003 | −0.008 | −0.015 | 0.672 → **0.660** |
| base | 17,319 | 0.000 | −0.002 | −0.003 | 0.396 → **0.387** |
| crab | 12,841 | −0.011 | −0.018 | −0.016 | 0.470 → 0.467 |
| invade | 8,253 | −0.020 | −0.032 | −0.024 | 0.506 → 0.506 |
| gank bot / mid / top | 7-8,000 | −0.01 / −0.01 / −0.01 | −0.01 / −0.01 / −0.03 | −0.03 / −0.01 / −0.03 | 0.599 → 0.592 · 0.584 → 0.584 · 0.556 → 0.551 |

- **The WP value according to the state isn't learned, at any horizon.** At 5 min the route weighs more, but everything that happens
  afterwards also comes in.
- **The risk of dying according to the state is**, in the frequent routes (clearing, fighting, going back).
- **The policy (what they choose) is**, and well.

That is why **a game's tree** (`routes.py game`) uses, for each route, its value in the finest cell that has at least 150 cases of
that route:

1. the moment;
2. from the 3rd camp, whether the enemy jungler is going to gank and where;
3. from the 7th, also health and gold.

Ganks, if the enemy isn't going to gank, are valued according to the wave of that lane. What can't be told apart from zero is marked
with ≈. Since it is an after-the-game analysis, it can use what the player didn't know at that moment (that the enemy was going to
gank). The policy, on the other hand, only uses what it saw.

---

## An example: the Qiyana of the review (EUW1-8008878706)

The whole tree is in `research/coaching/qiyana-EUW1-8008878706.routes.md`. Against what the author says:

| minute | the author | first version | now |
|---|---|---|---|
| 1:47 | recall after the 3rd camp, good | base 52% | base 58%, costs nothing |
| 2:56 | contest the crab, good | crab 85% | crab 84% |
| 3:08 | proactive play to mid, good | gank mid 42%, +0.6 | gank mid 41%, +0.4 at 90 s with the enemy mid ahead |
| 5:17 | dragon spot, good | objective 39% | objective 39% |
| 9:08 | (9:20) open to the grubs with the mid | objective, the first option | same: objective +2.4 at 90 s; she went back (11%) |
| 13:53 | invade and suffocate, good | invade 43% | invade 46%, +1.0 at 5 min (without becoming clear) |
| **6:10** | counter-gank to mid, good | **against**: gank mid −0.6 | **in favour**: it is a counter-gank (the enemy jungler was going to gank mid). In that state, +0.6 at 5 min against −0.6 for continuing to clear (by themselves they can't be told apart from zero) and −1.8 for going back; across all games, counter-ganking mid against continuing to clear is worth +0.7 at 90 s [+0.3, +1.2]. Only 5% of the high league would go: nobody had seen it |
| **8:44** | (8:36) it was time to go back | **against**: going back −0.7 | **can't be told apart**: with 34% health and 1,407 gold, going back and continuing to clear are worth the same (+0.2 and −0.2 at 5 min); the best by value was the crab |
| **10:30** | recall and open to the dragon, good | **against**: going back −0.7 | **can't be told apart**: with 48% health, going back and continuing to clear are worth the same |

Six out of nine matched. **Now it is seven, and none against.** The 8:44 and the 10:30 stay at "can't be told apart": with health at half,
the data don't say going back is better or worse than continuing.

---

## Limits

- **Association, not an experiment.** Whoever invades early may know something the state doesn't see (where the enemy started).
- **A route is the first thing it does.** A failed gank followed by a camp comes out as "gank" only if it reached to show up in the lane;
  otherwise, as "camp".
- **At 5 min what it did afterwards comes in**, not just the route.
- **The counter-gank is measured by where the enemy jungler was**, not by whether the player expected it. "They saw it" only counts their
  team's vision in the previous 10 s; tracking (deducing where it is from the missing camps) doesn't come in.
- **The champion enters as a feature**, but 5,000 games are few for a per-champion value.
- **Missing are features that matter**: the enemies' ultimates and the vision at each entry.

## Next

1. **Review 100 routes against the recordings**, with the counter-ganks among them, before using it in the coach.
2. **More games**: each user upload adds about 50 decisions. The state-by-state value is where it shows most; the table above has to be
   repeated when the corpus grows.
3. **In the coach**, mark only what is clear:
   - a route almost nobody chooses in that state and that is worth less with the interval far from zero;
   - going back to base with half health or more and under 800 gold;
   - a gank with prio, which doubles the risk of dying and costs at 5 min.

## Regenerate

```bash
# on the PC, resumable (about 45 minutes with 2 processes, in batches of 2 minutes)
python research/replays/routes.py rows research/ladder/data/routes2 --processes 2 --time-limit 115
python research/replays/routes.py merge research/ladder/data/routes2
# in a separate environment with scikit-learn (about 8 minutes with 2 cores)
python research/replays/routes.py analyse research/ladder/data/routes2 \
    --wp research/ladder/data/harvest-16.19/wp_per_second/wp_per_second.npz --model research/ladder/data/harvest-16.19/value/model.json
python research/replays/routes.py game research/ladder/data/routes2 EUW1-8008878706 Qiyana
```

Redone from the timeline, with the level now without gaps, in `research/ladder/data/routes3/` (`routes.py rows --timelines`): the tables change
only in the second decimal and the conclusions hold.

The first version (90 s, no counter-gank) is still in `research/ladder/data/routes/`.
