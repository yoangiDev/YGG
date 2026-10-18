# Catalogue: what the coach analyses and where it comes from

Which decisions, outcomes and states we are going to analyse with the decoded games, and which part of the data each thing uses. It serves
so as not to walk through the 5,264 games again every time a definition changes.

---

## The three layers

| layer | what it is | how much it costs to repeat |
|---|---|---|
| 1. Decode | the .rofl → `state.csv`, `events.json`, `vision.json`, `torres.json` (`lol-replay-decoder/cosecha.py`) | ~25 s per game: **~36 h** for all of them |
| 2. **The timeline** | `timeline.py extract`: one `.npz` per game with everything below | **1.5 s per game and process: ~65 min** with 2 processes on the PC |
| 3. The analyses | they read the timeline (`timeline.load`, or `rehydrate` for the older code) | see below |

Until now each analysis (`policy.py rows`, `routes.py rows`) did its own layer 2 over the decoded output: ~45 min per new idea, on the PC and
in batches of two minutes, because the 27 GB of decoded output are only there. **Layer 2 is only repeated if what it stores changes**
(`timeline.VERSION`), and layer 1 only if something is missing that the decoder doesn't produce.

**Done for the 5,265 games** (`research/ladder/data/timelines/`, version 4): **2.8 GB**, ~560 KB per game, without a single error. Taking up ten
times less than the decoded output, it fits in the analysis environment: it is carried over in nine packages and there each analysis runs in one go,
with no batches.

- **`routes.py rows --timelines`**: the 256,092 jungle decisions in **15 min** (before, ~45 min on the PC in batches).
- **`policy.py rows --timelines`**: the two million rows of the recall policy in **15 min**.
- A new analysis written directly over the timeline tables reads the whole corpus in 1-3 min.

**Checked against what there was before.** `routes.py` over the timeline produces the same 256,092 decisions as over the decoded output, and of its
80 columns 71 match in over 99.95%. What changes:

- **the level**, which before came out empty in 8.4% of the decisions (and with it the level difference, different in 2.3%). The decoder only writes
  a value when it changes and the code read the gap as "no data"; the timeline carries the last known value;
- and, below 0.5%, the route's exact second, when the enemy jungler was seen and who is alive in bot: when a second brings a half row, the timeline
  uses the last value and the earlier code took it as empty.

With the level corrected, the routes analysis (`routes3`) gives the same as before except in the second decimal, and the routes policy gets it right
just the same (62.7% on the first try).

**The decoder's level sometimes arrives late.** In a sample of 60 games, level 2 is marked more than 30 s after experience gives it in one of every
four level-ups (about 50 s median); the other levels, in 3%. For example, Qiyana comes out at level 1 with 485 experience, when 2 arrives at 280. Where
it matters, the level is derived from experience when reading the timeline, without redoing it.

`policy.py` over the timeline produces 2,021,913 rows in the same 5,264 games, against 2,021,904 before (2,021,884 coincide), and of its 39 columns 38
match in over 99.95%; health, in 99.94%. `policy.py` already filled in the gaps by itself. In addition, the game that used to fail for not carrying
`stats` comes in.

---

## What the timeline stores

| block | what | where from |
|---|---|---|
| champions, every second | place, health, mana, CS, camps, speed, level, unspent gold, total gold, experience, distance to the nearest ally and enemy; alive, seen by the enemy, Q/W/E/R and the two spells ready | `state.csv` + `vision.json` |
| waves, every second | where each lane's front is and how many living minions each side has | `moments.lane_waves` |
| deaths | who, who kills them, who hit them in the previous 10 s, when they respawn, where | `Death`, `UnitDeath`, `Damage` |
| recalls | when, whether cancelled, whether cut by an enemy, how close the enemy was | `moments.recalls` |
| camps and spawns | each monster that falls (who, where, on which side) and when each one spawns | `camps`, `SpawnNeutral` |
| turrets | place, lane, which one it is, when it falls and who takes it down; its health at each hit | `moments.turrets`, `torres.json` |
| wards | when, where, who, which item, when it dies | `CastSpell` + `SpawnMinion` |
| minions | each one: lane, wave, when it is born and dies, where, who kills it (champion or turret) and who collects | `moments.lane_waves` |
| fights | each fight: when, where, who is there, each side's gold, the deaths, each one's damage | `moments.fights` |
| damage, casts, controls | each hit between champions, each ability or spell (with its cooldown and where it points), each control | `Damage`, `CastSpell`, `controls` |
| economy | each purchase, each gold collected (and from what), each minion or monster finished, each attack | `BuyItem`, `Gold`, `creeps`, `attacks` |
| buffs | each buff a champion receives (the recall, those of objectives…), from whom and how long it lasts | `AddBuff` |
| headings | the destination of each click | `WaypointGroup` (see below) |

**It isn't there because the replay doesn't carry it**: pings, chat and the seconds left on a cooldown (only whether it is ready or not).

**The headings** only come in a game decoded with the recent decoder. On the ladder and in the 16.20 uploads the decoder only produced those of the
minions. Where each champion is heading is derived just the same from its place second by second, which is what is needed for "was heading to the
lane before the gank". Having the click's exact destination would require decoding again (~36 h); it is only worth it if some analysis really needs it.

---

## Decisions

| # | decision | who | when it is decided | options | uses from the timeline | status |
|---|---|---|---|---|---|---|
| 1 | Going back to base | everyone | every 10 s away from base | go back or continue | champions, waves, recalls, deaths | done (`policy.py`) |
| 2 | Jungle route | jungle | when the camps spawn and after each one, until 14:00 | camp, invade, crab, objective, gank, dive and counter-gank (lane), base | camps, champions, waves, damage, recalls, casts, wards | done (`routes.py`, 2nd version); the outcomes tree, 3rd version (`outcomes.py`) |
| 3 | **Covering a lane** (the conscious counter-gank) | jungle | when the enemy jungler approaches a lane | go before it arrives, carry on with its own or invade the other side | champions (place and direction of both junglers, seen), waves, fights | to do |
| 4 | Entering a fight | everyone | each fight | enter or not | fights, champions (spent gold, health, R and flash of both sides), deaths | done (`trees.py`), without the fine features |
| 5 | Showing up at an objective | everyone | the minute before an epic spawns | go or not | spawns, camps, champions, wards | done (`trees.py`) |
| 6 | Roam | mid, support | on leaving the lane | roam or stay | champions, waves, minions | half done (`openings.py`) |
| 7 | The wave before leaving | laners | before each recall or roam | push, freeze or leave it | waves, minions, last hits, recalls | there are pieces (`moments.stacks`, `freezes`) |
| 8 | Vision | everyone, above all support and jungle | each ward | where and when | wards, spawns, champions | there is data; `moments.vision` measures something |
| 9 | Flash and TP | everyone | each use | use or keep | casts (the spells' gaps), fights, deaths | tried (`value.md`) |
| 10 | After 14:00 | everyone | each stretch and before each objective | group, split, farm, baron | champions, turrets, waves, spawns | nothing yet (there are `moments.sidelanes`, `overgroup`) |
| 11 | Items | everyone | each purchase | what to buy | purchases, champions | low priority |

The full list of situations, what can be learned from each one and how your knowledge enters are in `situations.md`.

## Outcomes

The same for all decisions, and all of them come from the timeline **at any horizon**: neither the outcomes nor the horizons need to be fixed now.

The second version of the outcomes tree (`outcomes.py`) uses kills, deaths, flashes, camps, crabs, objectives, the lanes' CS, turret and plate gold,
and the jungler's health, mana and spent gold. Turret gold and mana can't be read on their own: they overlap with CS and with going back to base.

| outcome | where from |
|---|---|
| kills, deaths and assists (its own, its lane's, the team's) | deaths (killer and who hit) |
| summoner spells spent (the enemy's flash, its own) | casts, with each player's spells in `meta` |
| gold, experience and CS: its own against its opponent, the lane's and the team's | champions, every second |
| plates and turrets | turrets (health and fall), gold (what it is collected from) |
| objectives and camps (its own, stolen) | camps |
| wards placed and removed | wards |
| time dead | deaths (when it respawns) |
| the WP | `wp_per_second` (every 10 s); for new games it will have to be computed from the timeline |

## The state

Always split in three:

- **What it knew**: what its team saw, for the policy (what a good player would do with that information).
- **What was happening**: everything, for valuing after the game (the enemy jungler was going to gank, even if it didn't see it).
- **What it could deduce**: a model of where the enemy jungler is with what it knew (last seen, the missing camps, the timers). It is trained with each
  second of each game, because we know where it really was. It separates an informed decision from a bet: counter-ganking with the enemy at 70% in
  that zone is reading the game; with 15%, it worked out by luck.

## How it is valued

What was learned with the routes:

1. **Each option by its outcomes**: the probability of each according to the state, times what it is worth according to the WP model. Measuring the WP
   change of the whole team has too much noise for decisions that weigh 0.1-1 point.
2. **Compare in the same state**: what is expected isn't calibrated everywhere (with low health it comes out almost a point better than expected,
   whatever is done), so each option is compared with the others in its cell.
3. **Start from the idea that a decision weighs little**: each value starts from that of its zone and only moves away if the data ask for it.
4. **Measure the player's habits**: a decision of 0.5 points isn't seen in one game, but repeated in twenty it is.

---

## Order

1. ~~The whole timeline pass~~: done.
2. ~~Move `routes.py` and `policy.py` to read the timeline~~: done (`--timelines`), and checked above.
3. ~~The outcomes tree~~ of gank, counter-gank and invade: 1st version done (`outcomes.md`). What each outcome is worth and what usually happens with
   each route hold up with games it hasn't seen. It doesn't serve for the coach yet: it recommends ganking bot in 82% of the decisions, prio or not,
   because the routes are marked by what happened and outcomes are missing.
4. ~~Options by intent and the missing outcomes~~: 2nd version done (`outcomes.md`).
   - Options go by where the jungler is going, with the dive and the counter-gank apart.
   - The wave is the one that was seen and the one there will be on arriving.
   - It no longer says "always gank": continuing to clear comes out best in 72% of the decisions from the 3rd to the 6th camp.
   - What is measured directly gives what is expected: ganking bot with the wave crashing at its tower, −5.6 at 5 min; diving there, +1.7 at 90 s.
   - But the tree flattens the differences between states.
5. ~~Have the tree learn how each option changes with its state~~: 3rd version done (`outcomes.md`).
   - A separate model for going to a lane, with the wave, the flashes, the R, the abilities, its own wards, the levels and the champions of that lane.
   - The probability that the gank ends in a kill already gets it right state by state: from 23 to 65% for real between what it sees as hardest and
     easiest. Of the enemy's flash, what really weighs is 8 points.
   - Ganking no longer comes out overvalued on average.
   - The value in points state by state is still weak and changes between versions. For the review, for now, what is reliable is the probabilities.
6. ~~The value in points of each option~~: checked as far as the data go (`outcomes.md`).
   - The tree matches the measurement adjusted by who chooses each thing, in the 28 groups.
   - But in the trips to a lane, what is measured has ±0.8 to ±2.3 points of error, and the tree, decision by decision, isn't stable (0.15 to 0.21 between
     halves). Correcting it with what is measured is noise.
   - Going back to base is stable (0.77), and so is the gank's kill probability (0.84).
   - To measure each gank's value about 10 times more games would be needed.
   - The review is built with the probabilities and the value of going back to base.
7. **Covering a lane** (decision 3) and the model of where the enemy jungler is.
8. **The player's habits** over the author's games.
9. The rest of the decisions table, in order of what weighs most in the coach.

Before downloading more games, what has to be checked about the decoder is in `situations.md`.

```bash
# the timeline (on the PC; resumable, in 2-min batches; redoes those of another VERSION)
python research/replays/timeline.py extract research/ladder/data/timelines --processes 2 --time-limit 110
# check that it matches routes.py
python research/replays/timeline.py check research/ladder/data/timelines --routes research/ladder/data/routes2
# the earlier analyses, from the timeline (wherever the .npz are: on the PC or in the analysis environment)
python research/replays/routes.py rows <output> --timelines research/ladder/data/timelines --processes 2
python research/replays/policy.py rows <output> --timelines research/ladder/data/timelines --processes 2
```

To carry the timelines to the analysis environment: on the PC, `ls timelines/*.npz | split -l 600` and one `tar` per chunk (about 340 MB each, nine in
total); there, `tar xf` of each one.
